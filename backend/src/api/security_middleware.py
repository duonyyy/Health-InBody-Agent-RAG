"""Security headers and request size limiter middlewares for Health/InBody backend."""

import os
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """Add defense-in-depth HTTP security headers to all API responses."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        enable_hsts = (
            scope.get("scheme") == "https"
            or os.getenv("ENABLE_HSTS", "false").strip().lower() in {"1", "true", "yes", "on"}
        )
        path = scope.get("path", "")
        is_swagger_or_docs = path in {"/docs", "/redoc", "/openapi.json"}

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing_keys = {k.decode("latin-1").lower() for k, _ in headers}

                if "x-content-type-options" not in existing_keys:
                    headers.append((b"x-content-type-options", b"nosniff"))
                if "x-frame-options" not in existing_keys:
                    headers.append((b"x-frame-options", b"DENY"))
                if "referrer-policy" not in existing_keys:
                    headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                if "permissions-policy" not in existing_keys:
                    headers.append((b"permissions-policy", b"camera=(), microphone=(), geolocation=()"))
                if "x-xss-protection" not in existing_keys:
                    headers.append((b"x-xss-protection", b"0"))

                if enable_hsts and "strict-transport-security" not in existing_keys:
                    headers.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains"))

                if "content-security-policy" not in existing_keys:
                    if not is_swagger_or_docs:
                        headers.append((b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"))
                    else:
                        headers.append(
                            (
                                b"content-security-policy",
                                b"default-src 'self' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; frame-ancestors 'none'",
                            )
                        )

                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class ContentLengthLimitMiddleware:
    """Guard against denial-of-service memory exhaustion from oversized request payloads."""

    def __init__(self, app: ASGIApp, default_max_bytes: int = 2 * 1024 * 1024, upload_max_bytes: int = 15 * 1024 * 1024):
        self.app = app
        self.default_max_bytes = default_max_bytes
        self.upload_max_bytes = upload_max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "").lower()
            is_upload = "ocr" in path or "upload" in path or "import" in path
            max_allowed = self.upload_max_bytes if is_upload else self.default_max_bytes

            headers = Headers(scope=scope)
            content_length = headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > max_allowed:
                        response = JSONResponse(
                            status_code=413,
                            content={
                                "detail": f"Kích thước yêu cầu vượt quá giới hạn cho phép ({max_allowed // (1024 * 1024)}MB).",
                                "code": "payload_too_large",
                            },
                        )
                        await response(scope, receive, send)
                        return
                except ValueError:
                    pass

        await self.app(scope, receive, send)
