"""Shared corpus lifecycle admission, locking, write receipts, and release manifests.

This module is the single source of truth for:
1. R06 — Staging write admission and cross-process/container write vs activation locking.
2. R12 — Pre-upsert vector/payload validation and honest Qdrant write receipts.
3. R13 — Versioned corpus release manifests, canonical ID/content-hash set fingerprints,
   and embedding/chunking/resume compatibility checks.

No model names are hard-coded here; provider/model identifiers come strictly from
environment variables or caller-supplied metadata.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import socket
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from rag.qdrant.naming import COLLECTION_NAME_PATTERN

logger = logging.getLogger(__name__)

RELEASE_MANIFEST_SCHEMA_VERSION = 2
BM25_TOKENIZER_VERSION = "vi-nfd-alnum-v1"
CANONICAL_ID_SCHEMA_VERSION = "canonical-doc-chunk-v2"

_DEFAULT_PROTECTED_ALIAS = "nmk_chatbot_active"
_INVALID_VERSIONS = {"", "unknown", "unversioned", "none", "null", "latest", "default"}
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

DEFAULT_LOCK_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "corpus_locks"
)


class CorpusAdmissionError(ValueError):
    """Raised when a write or creation targets a protected or unapproved collection."""


class CorpusTopologyUnavailableError(RuntimeError):
    """Raised when live Qdrant alias/collection topology cannot be verified (fail-closed)."""


class CorpusLockError(RuntimeError):
    """Raised when a write lease or activation lock conflict prevents an operation."""


class CorpusWriteValidationError(ValueError):
    """Raised before Qdrant upsert when vectors, IDs, or payloads fail validation."""


class CorpusConflictError(ValueError):
    """Raised when resume encounters an existing point ID with different content/version."""


class CorpusReleaseMismatchError(RuntimeError):
    """Raised when runtime dense Qdrant release and lexical BM25 snapshot do not match."""


class QdrantWriteError(RuntimeError):
    """Raised when one or more Qdrant upsert batches fail or remain unconfirmed."""

    def __init__(self, message: str, *, receipt: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.receipt = receipt or {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_collection_name(name: str) -> bool:
    return bool(name and isinstance(name, str) and COLLECTION_NAME_PATTERN.fullmatch(name))


def normalize_corpus_version(value: Any) -> str:
    return str(value or "").strip()


def validate_corpus_version(value: Any) -> str:
    version = normalize_corpus_version(value)
    if version.lower() in _INVALID_VERSIONS:
        raise CorpusAdmissionError(
            "corpus_version tường minh và bất biến là bắt buộc cho mọi thao tác ghi corpus."
        )
    if len(version) > 128 or any(ch.isspace() for ch in version):
        raise CorpusAdmissionError(
            "corpus_version không hợp lệ (không chứa khoảng trắng và tối đa 128 ký tự)."
        )
    return version


def get_protected_serving_aliases(extra_aliases: Optional[Iterable[str]] = None) -> set[str]:
    """Collect all serving aliases protected by deployment configuration."""
    protected: set[str] = {_DEFAULT_PROTECTED_ALIAS}
    for env_key in ("QDRANT_COLLECTION_ALIAS", "QDRANT_COLLECTION_NAME"):
        raw = str(os.getenv(env_key, "")).strip()
        if raw:
            protected.add(raw)
    for item in str(os.getenv("CORPUS_PROTECTED_ALIASES", "")).split(","):
        cleaned = item.strip()
        if cleaned:
            protected.add(cleaned)
    if extra_aliases:
        for item in extra_aliases:
            cleaned = str(item or "").strip()
            if cleaned:
                protected.add(cleaned)
    return protected


def get_staging_allowlist(explicit_allowlist: Optional[Iterable[str]] = None) -> set[str]:
    """Return configured staging collection allowlist."""
    if explicit_allowlist is not None:
        return {str(item).strip() for item in explicit_allowlist if str(item or "").strip()}
    return {
        item.strip()
        for item in str(os.getenv("CORPUS_STAGING_COLLECTIONS", "")).split(",")
        if item.strip()
    }


def inspect_qdrant_aliases(qdrant_client: Any) -> Dict[str, str]:
    """Inspect live Qdrant aliases -> physical collection targets. Fails closed on error."""
    if qdrant_client is None:
        raise CorpusTopologyUnavailableError(
            "Không có Qdrant client để xác minh alias topology; từ chối ghi (fail-closed)."
        )
    if not hasattr(qdrant_client, "get_aliases"):
        raise CorpusTopologyUnavailableError(
            "Qdrant client không hỗ trợ get_aliases(); không thể xác minh đích ghi an toàn."
        )
    try:
        response = qdrant_client.get_aliases()
    except Exception as exc:
        raise CorpusTopologyUnavailableError(
            f"Không thể kiểm tra Qdrant alias topology ({type(exc).__name__}): {exc}"
        ) from exc

    aliases_raw = getattr(response, "aliases", response)
    if aliases_raw is None:
        return {}
    if not isinstance(aliases_raw, (list, tuple)):
        raise CorpusTopologyUnavailableError(
            "Phản hồi get_aliases() từ Qdrant không đúng định dạng mong đợi."
        )

    mapping: Dict[str, str] = {}
    for entry in aliases_raw:
        if isinstance(entry, Mapping):
            alias_name = str(entry.get("alias_name") or "").strip()
            collection_name = str(entry.get("collection_name") or "").strip()
        else:
            alias_name = str(getattr(entry, "alias_name", "") or "").strip()
            collection_name = str(getattr(entry, "collection_name", "") or "").strip()
        if alias_name and collection_name:
            mapping[alias_name] = collection_name
    return mapping


def verify_staging_write_target(
    target_collection: Optional[str],
    *,
    qdrant_client: Any = None,
    corpus_version: Optional[str] = None,
    require_corpus_version: bool = True,
    require_allowlist: bool = False,
    allowlist: Optional[Iterable[str]] = None,
    protected_aliases: Optional[Iterable[str]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Single admission gate enforced by API, Celery tasks, CLI importers, and data_pipeline.

    Guarantees:
    - Target collection must be explicitly specified and valid.
    - Serving alias names are always rejected (even if listed in staging allowlist).
    - For non-dry-run writes, live Qdrant alias topology MUST be queried (fail-closed).
    - Any collection that is an alias name OR the physical target of any active alias
      (especially protected serving aliases) is rejected — allowlist cannot override this.
    - Dry-run validates names/policy offline and explicitly flags `topology_verified=False`.
    """
    target = str(target_collection or "").strip()
    if not target:
        raise CorpusAdmissionError(
            "Đích ghi staging physical collection phải được chỉ định tường minh; không mặc định ghi vào serving alias."
        )
    if not _valid_collection_name(target):
        raise CorpusAdmissionError(
            f"Tên collection staging không hợp lệ: {target!r}."
        )

    protected = get_protected_serving_aliases(protected_aliases)
    if target in protected:
        raise CorpusAdmissionError(
            f"Từ chối ghi vào tên serving/protected alias {target!r}; chỉ được ghi vào physical staging collection."
        )

    configured_allowlist = get_staging_allowlist(allowlist)
    enforce_allowlist = require_allowlist or (
        str(os.getenv("CORPUS_ENFORCE_STAGING_ALLOWLIST", "false")).strip().lower()
        in {"1", "true", "yes", "on"}
    )
    if enforce_allowlist and target not in configured_allowlist:
        raise CorpusAdmissionError(
            f"Collection {target!r} không nằm trong CORPUS_STAGING_COLLECTIONS được phép ghi."
        )

    verified_version: Optional[str] = None
    if require_corpus_version and not dry_run:
        verified_version = validate_corpus_version(corpus_version)
    elif normalize_corpus_version(corpus_version):
        verified_version = normalize_corpus_version(corpus_version)

    if dry_run:
        return {
            "admitted": True,
            "target_collection": target,
            "corpus_version": verified_version,
            "dry_run": True,
            "topology_verified": False,
            "protected_aliases": sorted(protected),
            "active_aliases": {},
            "warning": "Offline dry-run: chưa xác minh Qdrant alias topology thật.",
        }

    # Live topology check — strictly fail closed.
    aliases = inspect_qdrant_aliases(qdrant_client)

    if target in aliases:
        raise CorpusAdmissionError(
            f"Từ chối ghi: {target!r} hiện là Qdrant alias trỏ tới {aliases[target]!r}, không phải physical staging collection."
        )

    for alias_name, physical_target in aliases.items():
        if physical_target == target:
            raise CorpusAdmissionError(
                f"Từ chối ghi: physical collection {target!r} đang được phục vụ qua alias {alias_name!r} "
                "(allowlist không được vượt qua bảo vệ actual alias target)."
            )

    return {
        "admitted": True,
        "target_collection": target,
        "corpus_version": verified_version,
        "dry_run": False,
        "topology_verified": True,
        "protected_aliases": sorted(protected),
        "active_aliases": dict(aliases),
        "warning": None,
    }


def _lock_dir(lock_dir: Optional[str | Path] = None) -> Path:
    if lock_dir is not None:
        return Path(lock_dir)
    env_dir = str(os.getenv("CORPUS_LOCK_DIR", "")).strip()
    if env_dir:
        return Path(env_dir)
    return DEFAULT_LOCK_DIR


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically write JSON with fsync and replace so readers never observe partial files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


@dataclass(frozen=True)
class CorpusLease:
    """Represents a cross-process/container filesystem lease for staging write or activation."""

    kind: str  # "write" or "activation"
    collection_name: str
    lease_id: str
    lock_path: Path
    owner: str
    release_id: Optional[str]
    corpus_version: Optional[str]
    alias_name: Optional[str]
    ttl_seconds: float
    acquired_at: str


class CorpusLeaseManager:
    """Cross-process/container mutual exclusion between staging writers and alias activation.

    Scope of guarantee:
    - Uses atomic `O_CREAT | O_EXCL` lock files in a shared directory (`CORPUS_LOCK_DIR`,
      defaulting to `backend/artifacts/corpus_locks`, mounted into both `chatbot-api` and
      `chatbot-worker` via `.:/usr/src/app/`).
    - Guarantees that within processes/containers sharing that directory:
      1. A collection with an active write lease cannot be activated.
      2. A collection undergoing activation cannot acquire a write lease.
      3. Two concurrent writers cannot write to the same staging collection simultaneously.
      4. Before every write batch, `verify_and_renew_write_lease` verifies lock ownership AND
         re-checks live Qdrant alias topology so an externally activated collection immediately
         halts further writes.
    - Limitation: If an external process runs on a separate host without mounting `CORPUS_LOCK_DIR`,
      the filesystem lock is not visible across hosts; only the per-batch Qdrant `get_aliases()`
      re-check protects against post-activation writes (with a narrow TOCTOU window between the
      re-check and the `upsert` RPC).
    """

    def __init__(
        self,
        lock_dir: Optional[str | Path] = None,
        *,
        default_ttl_seconds: float = 1800.0,
    ) -> None:
        self.lock_dir = _lock_dir(lock_dir)
        self.default_ttl_seconds = max(5.0, float(default_ttl_seconds))

    def _safe_name(self, name: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]", "_", str(name))

    def write_lock_path(self, collection_name: str) -> Path:
        return self.lock_dir / f"collection.{self._safe_name(collection_name)}.write.lock"

    def activation_lock_path(self, collection_name: str) -> Path:
        return self.lock_dir / f"collection.{self._safe_name(collection_name)}.activation.lock"

    def _read_lock(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"corrupt": True, "path": str(path)}

    def _is_expired(self, data: Mapping[str, Any], *, now_epoch: Optional[float] = None) -> bool:
        if data.get("corrupt"):
            return False
        now = time.time() if now_epoch is None else now_epoch
        expires = data.get("expires_at_epoch")
        if expires is None:
            return False
        return float(expires) < now

    def _reap_if_expired(self, path: Path) -> Optional[Dict[str, Any]]:
        existing = self._read_lock(path)
        if existing is None:
            return None
        if self._is_expired(existing):
            logger.warning(
                "Reaping expired corpus lock %s (lease_id=%s, owner=%s)",
                path.name,
                existing.get("lease_id"),
                existing.get("owner"),
            )
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return None
        return existing

    def _create_lock_exclusive(self, path: Path, payload: Mapping[str, Any]) -> None:
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        fd = os.open(str(path), flags, 0o600)
        try:
            encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def get_active_write_lease(self, collection_name: str) -> Optional[Dict[str, Any]]:
        return self._reap_if_expired(self.write_lock_path(collection_name))

    def get_active_activation_lock(self, collection_name: str) -> Optional[Dict[str, Any]]:
        return self._reap_if_expired(self.activation_lock_path(collection_name))

    def acquire_write_lease(
        self,
        collection_name: str,
        *,
        qdrant_client: Any,
        corpus_version: Optional[str] = None,
        release_id: Optional[str] = None,
        owner: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
        protected_aliases: Optional[Iterable[str]] = None,
        require_allowlist: bool = False,
        allowlist: Optional[Iterable[str]] = None,
        require_corpus_version: bool = True,
    ) -> CorpusLease:
        # 1. Fail-closed admission + live Qdrant alias check first.
        verify_staging_write_target(
            collection_name,
            qdrant_client=qdrant_client,
            corpus_version=corpus_version,
            require_corpus_version=require_corpus_version,
            require_allowlist=require_allowlist,
            allowlist=allowlist,
            protected_aliases=protected_aliases,
            dry_run=False,
        )

        # 2. Check no activation lock is currently held on this collection.
        active_activation = self.get_active_activation_lock(collection_name)
        if active_activation is not None:
            raise CorpusLockError(
                f"Collection {collection_name!r} đang trong quá trình activation "
                f"(lock={active_activation.get('lease_id')}); từ chối ghi."
            )

        # 3. Acquire exclusive write lock atomically.
        write_path = self.write_lock_path(collection_name)
        existing_write = self._reap_if_expired(write_path)
        if existing_write is not None:
            raise CorpusLockError(
                f"Collection {collection_name!r} đang có tiến trình ghi khác giữ lease "
                f"(lease_id={existing_write.get('lease_id')}, owner={existing_write.get('owner')})."
            )

        ttl = max(5.0, float(ttl_seconds or self.default_ttl_seconds))
        now = time.time()
        lease_id = str(uuid.uuid4())
        resolved_owner = owner or f"{socket.gethostname()}:{os.getpid()}"
        acquired_at = _utc_now_iso()
        payload = {
            "kind": "write",
            "collection_name": collection_name,
            "lease_id": lease_id,
            "owner": resolved_owner,
            "release_id": release_id,
            "corpus_version": corpus_version,
            "acquired_at": acquired_at,
            "updated_at": acquired_at,
            "expires_at_epoch": now + ttl,
        }
        try:
            self._create_lock_exclusive(write_path, payload)
        except FileExistsError as exc:
            raise CorpusLockError(
                f"Collection {collection_name!r} vừa bị tiến trình khác khóa ghi đồng thời."
            ) from exc

        lease = CorpusLease(
            kind="write",
            collection_name=collection_name,
            lease_id=lease_id,
            lock_path=write_path,
            owner=resolved_owner,
            release_id=release_id,
            corpus_version=corpus_version,
            alias_name=None,
            ttl_seconds=ttl,
            acquired_at=acquired_at,
        )

        # 4. Re-check activation lock and Qdrant topology AFTER acquiring lock to close race window.
        try:
            if self.get_active_activation_lock(collection_name) is not None:
                raise CorpusLockError(
                    f"Collection {collection_name!r} bắt đầu activation đồng thời; hủy write lease."
                )
            verify_staging_write_target(
                collection_name,
                qdrant_client=qdrant_client,
                corpus_version=corpus_version,
                require_corpus_version=require_corpus_version,
                require_allowlist=require_allowlist,
                allowlist=allowlist,
                protected_aliases=protected_aliases,
                dry_run=False,
            )
        except Exception:
            self.release_lease(lease)
            raise

        return lease

    def verify_and_renew_write_lease(
        self,
        lease: CorpusLease,
        *,
        qdrant_client: Any,
        protected_aliases: Optional[Iterable[str]] = None,
    ) -> None:
        """Called before EVERY upsert batch to ensure the collection is still a valid staging target."""
        current = self._read_lock(lease.lock_path)
        if not current or current.get("lease_id") != lease.lease_id:
            raise CorpusLockError(
                f"Write lease {lease.lease_id} cho collection {lease.collection_name!r} không còn hợp lệ hoặc đã bị thu hồi."
            )
        if self._is_expired(current):
            raise CorpusLockError(
                f"Write lease {lease.lease_id} cho collection {lease.collection_name!r} đã hết hạn; dừng ghi."
            )
        if self.get_active_activation_lock(lease.collection_name) is not None:
            raise CorpusLockError(
                f"Phát hiện activation lock trên {lease.collection_name!r}; dừng batch ghi."
            )

        # Live Qdrant alias re-check before batch write.
        verify_staging_write_target(
            lease.collection_name,
            qdrant_client=qdrant_client,
            corpus_version=lease.corpus_version,
            require_corpus_version=False,
            require_allowlist=False,
            protected_aliases=protected_aliases,
            dry_run=False,
        )

        # Renew lease atomically.
        updated = dict(current)
        updated["updated_at"] = _utc_now_iso()
        updated["expires_at_epoch"] = time.time() + lease.ttl_seconds
        atomic_write_json(lease.lock_path, updated)

    def acquire_activation_lock(
        self,
        collection_name: str,
        alias_name: str,
        *,
        release_id: Optional[str] = None,
        owner: Optional[str] = None,
        ttl_seconds: float = 300.0,
    ) -> CorpusLease:
        # 1. Refuse activation if a write lease is currently active on this collection!
        active_write = self.get_active_write_lease(collection_name)
        if active_write is not None:
            raise CorpusLockError(
                f"Không thể activate collection {collection_name!r}: đang có import/write lease hoạt động "
                f"(lease_id={active_write.get('lease_id')}, owner={active_write.get('owner')})."
            )

        act_path = self.activation_lock_path(collection_name)
        existing_act = self._reap_if_expired(act_path)
        if existing_act is not None:
            raise CorpusLockError(
                f"Collection {collection_name!r} đang có tiến trình activation khác "
                f"(lease_id={existing_act.get('lease_id')})."
            )

        ttl = max(5.0, float(ttl_seconds))
        now = time.time()
        lease_id = str(uuid.uuid4())
        resolved_owner = owner or f"{socket.gethostname()}:{os.getpid()}"
        acquired_at = _utc_now_iso()
        payload = {
            "kind": "activation",
            "collection_name": collection_name,
            "alias_name": alias_name,
            "lease_id": lease_id,
            "owner": resolved_owner,
            "release_id": release_id,
            "acquired_at": acquired_at,
            "updated_at": acquired_at,
            "expires_at_epoch": now + ttl,
        }
        try:
            self._create_lock_exclusive(act_path, payload)
        except FileExistsError as exc:
            raise CorpusLockError(
                f"Collection {collection_name!r} đang được activate bởi tiến trình khác."
            ) from exc

        lease = CorpusLease(
            kind="activation",
            collection_name=collection_name,
            lease_id=lease_id,
            lock_path=act_path,
            owner=resolved_owner,
            release_id=release_id,
            corpus_version=None,
            alias_name=alias_name,
            ttl_seconds=ttl,
            acquired_at=acquired_at,
        )

        # Re-check write lease AFTER acquiring activation lock to eliminate race window.
        if self.get_active_write_lease(collection_name) is not None:
            self.release_lease(lease)
            raise CorpusLockError(
                f"Không thể activate collection {collection_name!r}: phát hiện write lease xuất hiện đồng thời."
            )

        return lease

    def release_lease(self, lease: Optional[CorpusLease]) -> None:
        if lease is None:
            return
        current = self._read_lock(lease.lock_path)
        if current and current.get("lease_id") == lease.lease_id:
            try:
                lease.lock_path.unlink(missing_ok=True)
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDING & CANONICAL IDENTITY FINGERPRINTS
# ─────────────────────────────────────────────────────────────────────────────

def current_embedding_config(
    *,
    vector_size: Optional[int] = None,
    model_identifier: Optional[str] = None,
    model_revision: Optional[str] = None,
    normalize_embeddings: Optional[bool] = None,
    distance: str = "Cosine",
) -> Dict[str, Any]:
    """Build non-sensitive embedding configuration strictly from env/caller (model-agnostic)."""
    resolved_dim = int(vector_size or os.getenv("VECTOR_SIZE", "1024"))
    resolved_model = (
        str(model_identifier).strip()
        if model_identifier is not None and str(model_identifier).strip()
        else (
            str(os.getenv("EMBEDDING_MODEL_ID", "")).strip()
            or str(os.getenv("EMBEDDING_MODEL_NAME", "")).strip()
            or str(os.getenv("OPENAI_EMBEDDING_MODEL", "")).strip()
            or "configured_embedding_service"
        )
    )
    resolved_revision = (
        str(model_revision).strip()
        if model_revision is not None and str(model_revision).strip()
        else (str(os.getenv("EMBEDDING_MODEL_REVISION", "")).strip() or "unspecified")
    )
    if normalize_embeddings is None:
        resolved_norm = (
            str(os.getenv("EMBEDDING_NORMALIZE", "true")).strip().lower()
            in {"1", "true", "yes", "on"}
        )
    else:
        resolved_norm = bool(normalize_embeddings)

    max_length_raw = str(os.getenv("EMBEDDING_MAX_LENGTH", "")).strip()
    max_length = int(max_length_raw) if max_length_raw.isdigit() else None

    config: Dict[str, Any] = {
        "model_identifier": resolved_model,
        "model_revision": resolved_revision,
        "vector_size": resolved_dim,
        "distance": str(distance or "Cosine"),
        "normalize_embeddings": resolved_norm,
        "max_length": max_length,
    }
    if os.getenv("EMBEDDING_QUERY_PREFIX") or os.getenv("EMBEDDING_PASSAGE_PREFIX"):
        config["query_prefix"] = os.getenv("EMBEDDING_QUERY_PREFIX", "")
        config["passage_prefix"] = os.getenv("EMBEDDING_PASSAGE_PREFIX", "")
    config["fingerprint"] = compute_embedding_fingerprint(config)
    return config


def compute_embedding_fingerprint(config: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 fingerprint for embedding compatibility checks (not dim-only)."""
    material = {
        "model_identifier": str(config.get("model_identifier") or "").strip(),
        "model_revision": str(config.get("model_revision") or "unspecified").strip(),
        "vector_size": int(config.get("vector_size") or 0),
        "distance": str(config.get("distance") or "Cosine").strip().lower(),
        "normalize_embeddings": bool(config.get("normalize_embeddings", True)),
        "max_length": config.get("max_length"),
    }
    if config.get("query_prefix") or config.get("passage_prefix"):
        material["query_prefix"] = config.get("query_prefix", "")
        material["passage_prefix"] = config.get("passage_prefix", "")
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def canonical_chunk_identity(record: Mapping[str, Any]) -> Dict[str, str]:
    """Extract canonical (document_id, chunk_id, qdrant_point_id, content_hash) from any chunk/doc record.

    Handles legacy records where `doc_id` may have been overloaded with `chunk_id` in BM25
    while preserving explicit `document_id` and `chunk_id` without conflating the two.
    """
    nested = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}

    document_id = str(
        record.get("document_id")
        or nested.get("document_id")
        or nested.get("doc_id")
        or record.get("doc_id")
        or ""
    ).strip()

    chunk_id = str(
        record.get("chunk_id")
        or nested.get("chunk_id")
        or record.get("doc_id")
        or document_id
        or ""
    ).strip()

    if not document_id and chunk_id:
        document_id = chunk_id

    point_id = str(
        record.get("qdrant_point_id")
        or nested.get("qdrant_point_id")
        or (str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)) if chunk_id else "")
    ).strip()

    content = str(record.get("content") or record.get("page_content") or "")
    content_hash = str(
        record.get("content_hash")
        or nested.get("content_hash")
        or (hashlib.sha256(content.encode("utf-8")).hexdigest() if content else "")
    ).strip()

    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "qdrant_point_id": point_id,
        "content_hash": content_hash,
    }


def compute_chunk_set_fingerprint(records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Compute a deterministic fingerprint over the full set of canonical chunk identities.

    Two corpora with identical point count but any differing document_id, chunk_id,
    qdrant_point_id, or content_hash produce a different fingerprint.
    """
    rows: List[Tuple[str, str, str, str]] = []
    doc_ids: set[str] = set()
    chunk_ids: set[str] = set()
    duplicate_chunk_ids = 0

    for record in records:
        ident = canonical_chunk_identity(record)
        if ident["chunk_id"] in chunk_ids:
            duplicate_chunk_ids += 1
        if ident["document_id"]:
            doc_ids.add(ident["document_id"])
        if ident["chunk_id"]:
            chunk_ids.add(ident["chunk_id"])
        rows.append(
            (
                ident["qdrant_point_id"],
                ident["chunk_id"],
                ident["document_id"],
                ident["content_hash"],
            )
        )

    rows.sort()
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")

    return {
        "chunk_set_fingerprint": digest.hexdigest(),
        "total_chunks": len(rows),
        "unique_chunk_count": len(chunk_ids),
        "unique_document_count": len(doc_ids),
        "duplicate_chunk_ids": duplicate_chunk_ids,
    }


# ─────────────────────────────────────────────────────────────────────────────
# R12 — PRE-UPSERT VALIDATION & HONEST WRITE RECEIPTS
# ─────────────────────────────────────────────────────────────────────────────

def _is_valid_point_id(point_id: Any) -> bool:
    if isinstance(point_id, bool):
        return False
    if isinstance(point_id, int):
        return point_id >= 0
    if isinstance(point_id, str):
        cleaned = point_id.strip()
        if not cleaned:
            return False
        if _UUID_RE.fullmatch(cleaned):
            return True
        if cleaned.isdigit():
            return True
    return False


def validate_vector_values(
    vector: Any,
    *,
    expected_vector_size: Optional[int] = None,
    point_id: Any = None,
) -> List[float]:
    """Validate that a vector is non-empty, exact dimension, numeric, and finite (no NaN/Inf)."""
    if not isinstance(vector, (list, tuple)) or not vector:
        raise CorpusWriteValidationError(
            f"Point {point_id!r}: vector rỗng hoặc không phải danh sách số."
        )
    if expected_vector_size is not None and len(vector) != int(expected_vector_size):
        raise CorpusWriteValidationError(
            f"Point {point_id!r}: kích thước vector {len(vector)} != expected {expected_vector_size}."
        )
    validated: List[float] = []
    for idx, val in enumerate(vector):
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise CorpusWriteValidationError(
                f"Point {point_id!r}: phần tử vector[{idx}] không phải số thực hợp lệ."
            )
        fval = float(val)
        if not math.isfinite(fval):
            raise CorpusWriteValidationError(
                f"Point {point_id!r}: phần tử vector[{idx}] không hữu hạn (NaN/Inf)."
            )
        validated.append(fval)
    return validated


def validate_embeddings_alignment(
    items: Sequence[Any],
    embeddings: Any,
    *,
    expected_vector_size: Optional[int] = None,
) -> List[List[float]]:
    """Verify embeddings length matches input items exactly (never silently drop via zip)."""
    if not isinstance(embeddings, (list, tuple)):
        raise CorpusWriteValidationError("Dịch vụ embedding không trả về danh sách vector.")
    if len(embeddings) != len(items):
        raise CorpusWriteValidationError(
            f"Số lượng embedding ({len(embeddings)}) không khớp số chunk đầu vào ({len(items)})."
        )
    validated: List[List[float]] = []
    for idx, vec in enumerate(embeddings):
        validated.append(
            validate_vector_values(
                vec,
                expected_vector_size=expected_vector_size,
                point_id=f"batch_item_{idx}",
            )
        )
    return validated


def validate_vectors_before_upsert(
    vectors: Mapping[Any, Mapping[str, Any]],
    *,
    expected_vector_size: Optional[int] = None,
    expected_corpus_version: Optional[str] = None,
    expected_embedding_fingerprint: Optional[str] = None,
    require_canonical_payload: bool = False,
) -> None:
    """Validate every point ID, vector dimension/finiteness, and payload invariants before upsert."""
    if not vectors:
        raise CorpusWriteValidationError("Không có vector nào để ghi vào Qdrant.")

    inferred_dim = expected_vector_size
    for point_id, entry in vectors.items():
        if not _is_valid_point_id(point_id):
            raise CorpusWriteValidationError(
                f"Point ID không hợp lệ cho Qdrant: {point_id!r} (cần UUID hoặc số nguyên không âm)."
            )
        if not isinstance(entry, Mapping):
            raise CorpusWriteValidationError(f"Point {point_id!r}: cấu trúc bản ghi không hợp lệ.")
        vector = validate_vector_values(
            entry.get("vector"),
            expected_vector_size=inferred_dim,
            point_id=point_id,
        )
        if inferred_dim is None:
            inferred_dim = len(vector)

        payload = entry.get("payload")
        if not isinstance(payload, Mapping):
            raise CorpusWriteValidationError(f"Point {point_id!r}: thiếu payload dict.")

        if require_canonical_payload:
            if not str(payload.get("document_id") or "").strip():
                raise CorpusWriteValidationError(f"Point {point_id!r}: thiếu document_id.")
            if not str(payload.get("chunk_id") or "").strip():
                raise CorpusWriteValidationError(f"Point {point_id!r}: thiếu chunk_id.")
            chash = str(payload.get("content_hash") or "").strip()
            if not _HEX_SHA256_RE.fullmatch(chash):
                raise CorpusWriteValidationError(f"Point {point_id!r}: content_hash SHA-256 không hợp lệ.")

        if expected_corpus_version:
            actual_ver = str(payload.get("corpus_version") or "").strip()
            if actual_ver != expected_corpus_version:
                raise CorpusWriteValidationError(
                    f"Point {point_id!r}: payload corpus_version={actual_ver!r} != expected {expected_corpus_version!r}."
                )

        if expected_embedding_fingerprint:
            actual_fp = str(payload.get("embedding_fingerprint") or "").strip()
            if actual_fp and actual_fp != expected_embedding_fingerprint:
                raise CorpusWriteValidationError(
                    f"Point {point_id!r}: embedding_fingerprint không khớp cấu hình release."
                )


def interpret_qdrant_upsert_result(result: Any) -> Tuple[str, Optional[str]]:
    """Interpret Qdrant upsert return value honestly per qdrant-client UpdateStatus semantics.

    Returns (state, detail) where state is one of:
    - 'committed': Qdrant returned UpdateStatus.COMPLETED with wait=True.
    - 'acknowledged_uncommitted': Qdrant returned UpdateStatus.ACKNOWLEDGED (queued, NOT wait-applied).
    - 'unverified_client_return': Stub/mock returned None or boolean True without UpdateResult.
    - 'failed': UpdateStatus.WAIT_TIMEOUT, explicit error dict, False, or unknown status.
    """
    if result is None:
        return "unverified_client_return", "client returned None without UpdateResult status"
    if isinstance(result, bool):
        return ("unverified_client_return", "boolean_true") if result else ("failed", "upsert returned False")
    if isinstance(result, Mapping):
        if result.get("error"):
            return "failed", str(result["error"])
        status_raw = str(result.get("status") or "").strip().lower()
        if status_raw in {"completed", "ok"}:
            return "committed", status_raw
        if status_raw == "acknowledged":
            return "acknowledged_uncommitted", "Qdrant returned acknowledged (not completed)"
        if status_raw in {"wait_timeout", "failed", "error"}:
            return "failed", f"Qdrant upsert status={status_raw}"
        return "failed", f"Unrecognized upsert response status={status_raw!r}"

    status_attr = getattr(result, "status", None)
    if status_attr is not None:
        status_val = str(getattr(status_attr, "value", status_attr)).strip().lower()
        if status_val == "completed":
            return "committed", "completed"
        if status_val == "acknowledged":
            return "acknowledged_uncommitted", "Qdrant returned acknowledged (not wait-completed)"
        if status_val == "wait_timeout":
            return "failed", "Qdrant upsert wait_timeout"
        return "failed", f"Unexpected Qdrant UpdateStatus={status_val!r}"

    return "failed", f"Unsupported Qdrant upsert return type: {type(result).__name__}"


def new_write_receipt(
    *,
    collection_name: str,
    corpus_version: Optional[str] = None,
    release_id: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "status": "dry_run" if dry_run else "pending",
        "collection_name": collection_name,
        "corpus_version": corpus_version,
        "release_id": release_id,
        "dry_run": dry_run,
        "attempted_points": 0,
        "acknowledged_points": 0,
        "committed_points": 0,
        "verified_points": 0,
        "failed_points": 0,
        "unconfirmed_points": 0,
        "skipped_points": 0,
        "skipped_reasons": {},
        "conflict_points": 0,
        "batches_attempted": 0,
        "batches_committed": 0,
        "batches_unconfirmed": 0,
        "batches_failed": 0,
        "partial_write": False,
        "rollback_performed": False,
        "errors": [],
        "batch_receipts": [],
    }


def record_skip(receipt: Dict[str, Any], reason: str, count: int = 1) -> None:
    receipt["skipped_points"] += count
    reasons = receipt.setdefault("skipped_reasons", {})
    reasons[reason] = int(reasons.get(reason, 0)) + count


def finalize_write_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    """Compute honest ok/status/partial_write flags from actual batch counts."""
    if receipt.get("dry_run"):
        has_error = bool(receipt.get("errors")) or receipt.get("failed_points", 0) > 0 or receipt.get("conflict_points", 0) > 0
        receipt["ok"] = not has_error
        receipt["status"] = "failed" if has_error else "dry_run"
        receipt["partial_write"] = False
        return receipt

    attempted = int(receipt.get("attempted_points", 0))
    committed = int(receipt.get("committed_points", 0))
    acknowledged = int(receipt.get("acknowledged_points", 0))
    failed = int(receipt.get("failed_points", 0))
    unconfirmed = int(receipt.get("unconfirmed_points", 0))
    conflicts = int(receipt.get("conflict_points", 0))
    skipped = int(receipt.get("skipped_points", 0))
    has_errors = bool(receipt.get("errors")) or failed > 0 or conflicts > 0

    wrote_any = committed > 0 or acknowledged > 0
    receipt["partial_write"] = bool(wrote_any and (has_errors or unconfirmed > 0))
    receipt["rollback_performed"] = False

    if failed > 0 or conflicts > 0:
        receipt["ok"] = False
        receipt["status"] = "partial" if wrote_any else "failed"
    elif unconfirmed > 0:
        receipt["ok"] = False
        receipt["status"] = "incomplete"
    elif has_errors:
        receipt["ok"] = False
        receipt["status"] = "partial" if wrote_any else "failed"
    elif attempted == 0 and skipped > 0:
        receipt["ok"] = True
        receipt["status"] = "skipped"
    elif attempted == 0 and skipped == 0:
        receipt["ok"] = True
        receipt["status"] = "no_op"
    elif committed == attempted:
        receipt["ok"] = True
        receipt["status"] = "committed"
    elif acknowledged == attempted and receipt.get("batches_unconfirmed", 0) == 0:
        receipt["ok"] = True
        receipt["status"] = "acknowledged_unverified"
    else:
        receipt["ok"] = False
        receipt["status"] = "incomplete"

    return receipt


# ─────────────────────────────────────────────────────────────────────────────
# CHECKPOINT & RESUME COMPATIBILITY
# ─────────────────────────────────────────────────────────────────────────────

def build_resume_signature(
    *,
    collection_name: str,
    corpus_version: str,
    data_file_sha256: str,
    chunk_size: int,
    chunk_overlap: int,
    vector_size: int,
    embedding_fingerprint: str,
    splitter_version: str = "default",
) -> Dict[str, Any]:
    return {
        "collection_name": str(collection_name),
        "corpus_version": str(corpus_version),
        "data_file_sha256": str(data_file_sha256),
        "chunk_size": int(chunk_size),
        "chunk_overlap": int(chunk_overlap),
        "vector_size": int(vector_size),
        "embedding_fingerprint": str(embedding_fingerprint),
        "splitter_version": str(splitter_version),
    }


def verify_resume_compatibility(
    existing_checkpoint: Mapping[str, Any],
    expected_signature: Mapping[str, Any],
) -> None:
    """Reject resume if source file, chunking, version, collection, or embedding config changed."""
    prior = existing_checkpoint.get("resume_signature")
    if not isinstance(prior, Mapping):
        raise CorpusConflictError("Checkpoint thiếu resume_signature; cần tạo staging release mới")
    required = {"collection_name", "corpus_version", "data_file_sha256", "chunk_size",
                "chunk_overlap", "vector_size", "embedding_fingerprint", "splitter_version"}
    for signature in (prior, expected_signature):
        valid = required.issubset(signature)
        for field in required - {"chunk_size", "chunk_overlap", "vector_size"}:
            value = signature.get(field)
            valid = valid and isinstance(value, str) and bool(value.strip())
        for field in ("data_file_sha256", "embedding_fingerprint"):
            valid = valid and bool(re.fullmatch(r"[0-9a-f]{64}", str(signature.get(field) or "")))
        for field in ("chunk_size", "chunk_overlap", "vector_size"):
            value = signature.get(field)
            valid = valid and type(value) is int and value >= (0 if field == "chunk_overlap" else 1)
        if not valid or signature["chunk_overlap"] >= signature["chunk_size"]:
            raise CorpusConflictError("Resume signature thiếu hoặc sai schema; cần tạo staging release mới")
    mismatches: List[str] = []
    for key, expected_val in expected_signature.items():
        if key not in prior or prior.get(key) is None or (isinstance(prior.get(key), str) and not prior[key].strip()):
            mismatches.append(f"{key}: missing in checkpoint")
            continue
        if prior.get(key) != expected_val:
            mismatches.append(f"{key}: checkpoint={prior.get(key)!r} != current={expected_val!r}")
    if mismatches:
        raise CorpusConflictError(
            "Không thể resume từ checkpoint cũ vì cấu hình/nguồn đã thay đổi "
            "(cần tạo staging release mới): " + "; ".join(mismatches)
        )


def check_existing_point_conflict(
    point_id: str,
    expected_payload: Mapping[str, Any],
    existing_fingerprints: Mapping[str, Mapping[str, Any]],
) -> Tuple[str, Optional[str]]:
    """Determine whether an existing point in staging can be safely skipped or is a conflict.

    Returns:
    - ("missing", None): point does not exist in target collection -> embed & upsert.
    - ("match", None): point exists AND content_hash + corpus_version + embedding_fingerprint match -> safe skip.
    - ("conflict", reason): point ID exists with different content/version/fingerprint or missing hash!
    """
    existing = existing_fingerprints.get(point_id)
    if existing is None:
        return "missing", None

    for payload in (expected_payload, existing):
        try:
            validate_corpus_version(payload.get("corpus_version"))
        except CorpusAdmissionError:
            return "conflict", f"point_id={point_id}: corpus_version không hợp lệ"

    for field in ("qdrant_point_id", "document_id", "chunk_id", "content_hash", "corpus_version", "embedding_fingerprint"):
        expected = expected_payload.get(field)
        actual = existing.get(field)
        if not isinstance(expected, str) or not expected.strip() or not isinstance(actual, str) or not actual.strip():
            return "conflict", f"point_id={point_id}: thiếu {field}"
        if expected != actual or (field == "qdrant_point_id" and expected != point_id):
            return "conflict", f"point_id={point_id}: {field} không khớp"
        if field in {"content_hash", "embedding_fingerprint"} and not re.fullmatch(r"[0-9a-f]{64}", expected):
            return "conflict", f"point_id={point_id}: {field} không hợp lệ"

    return "match", None


# ─────────────────────────────────────────────────────────────────────────────
# R13 — VERSIONED CORPUS RELEASE MANIFEST
# ─────────────────────────────────────────────────────────────────────────────

def make_release_id(corpus_version: str, chunk_set_fingerprint: Optional[str] = None) -> str:
    safe_ver = re.sub(r"[^A-Za-z0-9._-]", "-", str(corpus_version or "unversioned"))
    suffix = (chunk_set_fingerprint or uuid.uuid4().hex)[:12]
    return f"rel-{safe_ver}-{suffix}"


def build_release_manifest(
    *,
    corpus_version: str,
    physical_collection: str,
    serving_alias: str = _DEFAULT_PROTECTED_ALIAS,
    release_id: Optional[str] = None,
    source_manifest: Optional[Mapping[str, Any]] = None,
    chunk_manifest: Optional[Mapping[str, Any]] = None,
    chunking_config: Optional[Mapping[str, Any]] = None,
    embedding_config: Optional[Mapping[str, Any]] = None,
    bm25_artifact: Optional[Mapping[str, Any]] = None,
    provenance_summary: Optional[Mapping[str, Any]] = None,
    eval_binding: Optional[Mapping[str, Any]] = None,
    write_receipt: Optional[Mapping[str, Any]] = None,
    build_status: str = "building",
    publication_status: str = "staging",
    verification: Optional[Mapping[str, Any]] = None,
    previous_release: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a versioned corpus release manifest binding source -> chunks -> Qdrant -> BM25 -> eval."""
    verified_version = validate_corpus_version(corpus_version)
    if not _valid_collection_name(physical_collection):
        raise CorpusAdmissionError(f"Invalid physical_collection: {physical_collection!r}")
    if physical_collection == serving_alias:
        raise CorpusAdmissionError(
            "physical_collection trong release manifest phải khác serving_alias."
        )

    chunk_fp = (chunk_manifest or {}).get("chunk_set_fingerprint")
    resolved_release_id = release_id or make_release_id(verified_version, chunk_fp)
    emb_cfg = dict(embedding_config or current_embedding_config())
    if "fingerprint" not in emb_cfg:
        emb_cfg["fingerprint"] = compute_embedding_fingerprint(emb_cfg)

    now = _utc_now_iso()
    return {
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
        "release_id": resolved_release_id,
        "corpus_version": verified_version,
        "physical_collection": physical_collection,
        "serving_alias": serving_alias,
        "created_at": now,
        "updated_at": now,
        "canonical_id_schema": CANONICAL_ID_SCHEMA_VERSION,
        "source_manifest": dict(source_manifest or {}),
        "chunk_manifest": dict(chunk_manifest or {}),
        "chunking_config": dict(chunking_config or {}),
        "embedding_config": emb_cfg,
        "bm25_artifact": dict(bm25_artifact or {}),
        "provenance_summary": dict(provenance_summary or {}),
        "eval_binding": dict(
            eval_binding
            or {
                "suite_path": None,
                "suite_version": None,
                "suite_sha256": None,
                "label_granularity": None,
                "status": "not_run",
                "last_eval_at": None,
                "report_sha256": None,
            }
        ),
        "write_receipt": dict(write_receipt or {}),
        "build_status": build_status,
        "publication_status": publication_status,
        "verification": dict(
            verification
            or {
                "verified_at": None,
                "qdrant_verified": False,
                "bm25_verified": False,
                "count_matched": False,
                "fingerprint_matched": False,
                "payload_indexes_verified": False,
                "errors": [],
            }
        ),
        "previous_release": dict(previous_release or {}),
    }


def load_release_manifest(path: str | Path) -> Dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Release manifest not found: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_release_manifest(data)
    return data


def save_release_manifest(path: str | Path, manifest: Mapping[str, Any]) -> None:
    validate_release_manifest(manifest)
    updated = dict(manifest)
    updated["updated_at"] = _utc_now_iso()
    atomic_write_json(Path(path), updated)


def validate_release_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate structural invariants of a corpus release manifest."""
    if not isinstance(manifest, Mapping):
        raise ValueError("Release manifest must be a JSON object")
    if manifest.get("schema_version") != RELEASE_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported release manifest schema_version={manifest.get('schema_version')!r}"
        )
    for field in ("release_id", "corpus_version", "physical_collection", "serving_alias"):
        if not str(manifest.get(field) or "").strip():
            raise ValueError(f"Release manifest missing required field: {field}")
    if manifest["physical_collection"] == manifest["serving_alias"]:
        raise ValueError("Release manifest physical_collection must differ from serving_alias")
    emb = manifest.get("embedding_config") or {}
    if not str(emb.get("fingerprint") or "").strip():
        raise ValueError("Release manifest missing embedding_config.fingerprint")
    if int(emb.get("vector_size") or 0) <= 0:
        raise ValueError("Release manifest embedding_config.vector_size must be positive")


def check_release_activation_ready(
    manifest: Mapping[str, Any],
    *,
    require_verified_eval: bool = False,
) -> List[str]:
    """Return list of blocking reasons why a release manifest is not eligible for activation."""
    errors: List[str] = []
    try:
        validate_release_manifest(manifest)
    except ValueError as exc:
        return [str(exc)]

    if manifest.get("build_status") not in {"imported", "verified"}:
        errors.append(f"build_status={manifest.get('build_status')!r} chưa hoàn tất")

    receipt = manifest.get("write_receipt") or {}
    if receipt:
        if not receipt.get("ok"):
            errors.append(f"write_receipt.ok is False (status={receipt.get('status')!r})")
        if int(receipt.get("failed_points") or 0) > 0:
            errors.append(f"write_receipt có {receipt.get('failed_points')} failed_points")
        if int(receipt.get("conflict_points") or 0) > 0:
            errors.append(f"write_receipt có {receipt.get('conflict_points')} conflict_points")
        if int(receipt.get("unconfirmed_points") or 0) > 0:
            errors.append(f"write_receipt có {receipt.get('unconfirmed_points')} unconfirmed_points")

    chunk_manifest = manifest.get("chunk_manifest") or {}
    expected_count = int(chunk_manifest.get("expected_count") or 0)
    expected_fp = str(chunk_manifest.get("chunk_set_fingerprint") or "").strip()
    if expected_count <= 0:
        errors.append("chunk_manifest.expected_count phải > 0")
    if not _HEX_SHA256_RE.fullmatch(expected_fp):
        errors.append("chunk_manifest.chunk_set_fingerprint không hợp lệ")

    bm25 = manifest.get("bm25_artifact") or {}
    if bm25:
        if bm25.get("chunk_set_fingerprint") != expected_fp:
            errors.append("bm25_artifact.chunk_set_fingerprint không khớp chunk_manifest")
        if int(bm25.get("document_count") or 0) != expected_count:
            errors.append("bm25_artifact.document_count không khớp chunk_manifest.expected_count")
        if bm25.get("physical_collection") not in (None, "", manifest.get("physical_collection")):
            errors.append("bm25_artifact.physical_collection không khớp release physical_collection")
        if bm25.get("corpus_version") != manifest.get("corpus_version"):
            errors.append("bm25_artifact.corpus_version không khớp release corpus_version")

    verification = manifest.get("verification") or {}
    if verification.get("errors"):
        errors.append(f"verification có lỗi: {verification.get('errors')}")

    if require_verified_eval:
        eval_binding = manifest.get("eval_binding") or {}
        if eval_binding.get("status") != "verified":
            errors.append(
                f"eval_binding.status={eval_binding.get('status')!r} chưa đạt 'verified'"
            )

    return errors
