"""Render Compose with synthetic env files only; never read private deployment envs."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILES = ["frontend/docker-compose.yml", "backend/docker-compose.yml",
                 "infra/docker-compose.infra.yml", "infra/embed_serving/docker-compose.serving.yml",
                 "infra/embed_serving/docker-compose.gpu.yml"]


def template_values(path):
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#") and "=" in line)


@pytest.fixture
def compose(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose CLI is not installed")
    version = subprocess.run(["docker", "compose", "version"], capture_output=True, timeout=30)
    if version.returncode:
        pytest.skip("Docker Compose CLI is not available")
    env = os.environ.copy()
    for relative in COMPOSE_FILES:
        source = (ROOT / relative).read_text(encoding="utf-8")
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        # Shell variables take precedence over --env-file. Remove only keys
        # referenced by these files so test results cannot depend on the host.
        for key in re.findall(r"\$\{([A-Z][A-Z0-9_]*)", source):
            env.pop(key, None)
    for key in ("COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "COMPOSE_ENV_FILES"):
        env.pop(key, None)
    (tmp_path / "infra/embed_serving/.env.serving").write_text("", encoding="utf-8")

    def render(relative, values=None, *, expected_exit=0, overrides=()):
        data = {"POSTGRES_PASSWORD": "synthetic-password-only", "DATABASE_URL": "sqlite://",
                **(values or {})}
        env_file = tmp_path / "backend/.env"
        env_file.write_text("\n".join(f"{key}={value}" for key, value in data.items()), encoding="utf-8")
        command = ["docker", "compose", "--project-name", "fix04-config-test", "--env-file", str(env_file)]
        for filename in (relative, *overrides):
            command.extend(["-f", str(tmp_path / filename)])
        result = subprocess.run(
            command + ["config", "--format", "json"],
            cwd=tmp_path, env=env, text=True, capture_output=True, timeout=30,
        )
        if expected_exit:
            assert result.returncode != 0
            return result.stderr
        assert result.returncode == 0, result.stderr  # Synthetic values only.
        return json.loads(result.stdout)

    return render


def test_frontend_defaults_are_browser_url_and_production_build_args(compose):
    service = compose("frontend/docker-compose.yml")["services"]["chatbot-next-ui"]
    assert isinstance(service["build"], dict)
    assert service["build"].get("args", {}).get("NEXT_PUBLIC_API_URL") == "http://localhost:8000"
    assert service["build"]["args"]["NEXT_PUBLIC_AUTH_MODE"] == "production"
    assert not any(key.startswith("NEXT_PUBLIC_") for key in service.get("environment", {}))


def test_explicit_frontend_config_is_forwarded_at_build_time(compose):
    public = {"NEXT_PUBLIC_API_URL": "https://api.fix04.invalid", "NEXT_PUBLIC_AUTH_MODE": "development",
              "NEXT_PUBLIC_DEV_USER_ID": "synthetic-dev"}
    service = compose("frontend/docker-compose.yml", public)["services"]["chatbot-next-ui"]
    assert service["build"].get("args") == public


@pytest.mark.parametrize("relative", ["infra/docker-compose.infra.yml",
                                       "infra/embed_serving/docker-compose.serving.yml"])
def test_data_and_embedding_host_ports_are_loopback(compose, relative):
    config = compose(relative)
    ports = [port for service in config["services"].values() for port in service.get("ports", [])]
    assert ports
    assert all(port.get("host_ip") == "127.0.0.1" for port in ports)


def test_postgres_requires_explicit_nonempty_password(compose):
    stderr = compose("infra/docker-compose.infra.yml", {"POSTGRES_PASSWORD": ""}, expected_exit=1)
    assert "POSTGRES_PASSWORD" in stderr


def test_gpu_override_keeps_standalone_embedding_ports_local(compose):
    service = compose("infra/embed_serving/docker-compose.serving.yml",
                      overrides=["infra/embed_serving/docker-compose.gpu.yml"])["services"]["embedding-api"]
    assert service["environment"]["EMBEDDING_DEVICE"] == "cuda"
    assert all(port.get("host_ip") == "127.0.0.1" for port in service["ports"])


def test_backend_envfile_is_not_overridden_by_compose_defaults(compose):
    values = {"AUTH_MODE": "development", "LLM_PROVIDER": "custom", "DATABASE_URL": "sqlite://",
              "CORS_ALLOWED_ORIGINS": "https://ui.fix04.invalid", "JWT_ISSUER": "synthetic-issuer",
              "JWT_AUDIENCE": "synthetic-web", "JWT_SIGNING_KEY": "synthetic-only-" + "x" * 64}
    services = compose("backend/docker-compose.yml", values)["services"]
    for name in ("chatbot-api", "chatbot-worker", "chatbot-scheduler"):
        assert all(services[name]["environment"].get(key) == value for key, value in values.items())


def test_backend_template_requires_private_credentials_and_documents_local_cors():
    values = template_values(ROOT / "backend/.env.example")
    assert values["AUTH_MODE"] == "production"
    assert values["POSTGRES_PASSWORD"] == ""
    assert values["DATABASE_URL"] == ""
    assert values["JWT_SIGNING_KEY"] == ""
    assert values["JWT_ISSUER"] and values["JWT_AUDIENCE"]
    assert set(values["CORS_ALLOWED_ORIGINS"].split(",")) == {
        "http://localhost:3000", "http://127.0.0.1:3000"}


@pytest.mark.parametrize("allowed", [True, False])
def test_production_cors_and_auth_boundary_from_example(allowed):
    env = os.environ.copy()
    env.update(template_values(ROOT / "backend/.env.example"))
    env.update(PYTHONPATH=str(ROOT / "backend/src"), DATABASE_URL="sqlite://", LLM_PROVIDER="none",
               CUSTOM_EMBEDDING_ENABLED="false", JWT_SIGNING_KEY="synthetic-only-" + "k" * 64,
               TEST_ORIGIN="http://localhost:3000" if allowed else "https://untrusted.fix04.invalid",
               TEST_EXPECTED="200" if allowed else "400")
    code = r'''
import os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi.testclient import TestClient
from api.app import app
from memory import chat
def forbidden(*args, **kwargs):
    raise AssertionError("Rejected auth must never read storage")
chat.profiles.safe_build_confirmed_context = forbidden
client = TestClient(app)
origin = os.environ["TEST_ORIGIN"]
headers = {"Origin": origin, "Access-Control-Request-Method": "POST",
           "Access-Control-Request-Headers": "authorization,content-type"}
preflight = client.options("/auth/login", headers=headers)
assert preflight.status_code == int(os.environ["TEST_EXPECTED"])
assert preflight.headers.get("access-control-allow-origin") == (origin if preflight.status_code == 200 else None)
now = datetime.now(timezone.utc)
claims = {"sub": "synthetic-fix04", "iss": os.environ["JWT_ISSUER"], "aud": os.environ["JWT_AUDIENCE"],
          "iat": now, "nbf": now, "exp": now + timedelta(minutes=5), "jti": "synthetic"}
for token in [None, jwt.encode(claims, "wrong-synthetic-" + "w" * 64, algorithm="HS256"),
              jwt.encode({**claims, "exp": now-timedelta(seconds=1)}, os.environ["JWT_SIGNING_KEY"], algorithm="HS256")]:
    headers = {"Origin": origin, "X-Dev-User-Id": "untrusted-user"}
    if token:
        headers["Authorization"] = "Bearer " + token
    response = client.post("/agent/answer", headers=headers, json={"question": "Xin chào"})
    assert response.status_code == 401
'''
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=40)
    # Do not forward subprocess output: a failing HTTP assertion should never
    # dump JWTs, environment values or health payloads into the test report.
    assert result.returncode == 0, "Production CORS/auth boundary check failed"


def test_setup_secret_generation_is_quiet_and_refuses_overwrite(tmp_path):
    setup = (ROOT / "SETUP.md").read_text(encoding="utf-8")
    match = re.search(r"```powershell\n@'\n(.*?)\n'@ \| python -B -", setup, flags=re.S)
    assert match, "SETUP must provide a runnable private-env initialization example"
    (tmp_path / "backend").mkdir()
    shutil.copyfile(ROOT / "backend/.env.example", tmp_path / "backend/.env.example")
    first = subprocess.run([sys.executable, "-B", "-c", match.group(1)], cwd=tmp_path,
                           capture_output=True, timeout=10)
    assert first.returncode == 0, "Documented setup command failed"
    assert not first.stdout and not first.stderr, "Setup must not print private values"
    target = tmp_path / "backend/.env"
    snapshot = target.read_bytes()
    values = template_values(target)
    assert len(values["JWT_SIGNING_KEY"]) >= 64
    assert len(values["POSTGRES_PASSWORD"]) >= 64
    assert values["JWT_SIGNING_KEY"] != values["POSTGRES_PASSWORD"]
    assert values["POSTGRES_PASSWORD"] in values["DATABASE_URL"]
    second = subprocess.run([sys.executable, "-B", "-c", match.group(1)], cwd=tmp_path,
                            capture_output=True, timeout=10)
    assert second.returncode != 0, "Existing credentials must be preserved"
    assert target.read_bytes() == snapshot
