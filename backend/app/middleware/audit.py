"""
Structured audit logging middleware.

Logs every HTTP request and key security events in JSON format.
Captures: timestamp, method, path, status, duration, IP, actor DID, event type.
"""
import json
import logging
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# ── Context variable to carry audit context through the request lifecycle ────
_audit_ctx: ContextVar[Dict[str, Any]] = ContextVar("audit_ctx", default={})

# ── Dedicated audit logger ────────────────────────────────────────────────────
audit_logger = logging.getLogger("oslt.audit")
audit_logger.setLevel(logging.INFO)


class JSONAuditFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        # Merge extra fields from audit context
        extra = getattr(record, "audit_extra", {})
        entry.update(extra)
        return json.dumps(entry, default=str)


# Attach JSON formatter to the audit logger (idempotent)
def _ensure_handler() -> None:
    if not audit_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONAuditFormatter())
        audit_logger.addHandler(handler)
        audit_logger.propagate = False


_ensure_handler()


# ── Helper: emit a structured audit event ────────────────────────────────────
def audit_event(
    event: str,
    *,
    actor_did: Optional[str] = None,
    detail: Optional[str] = None,
    severity: str = "INFO",
    **extra: Any,
) -> None:
    """
    Emit a structured audit log entry.

    Args:
        event: Event type (e.g., "auth.success", "rate_limit.blocked", "request")
        actor_did: DID of the acting party (if known)
        detail: Human-readable detail string
        severity: Log level (INFO, WARNING, ERROR, CRITICAL)
        **extra: Additional key-value pairs to include in the log entry
    """
    fields: Dict[str, Any] = {
        "event": event,
    }
    if actor_did:
        fields["actor_did"] = actor_did
    if detail:
        fields["detail"] = detail
    fields.update(extra)

    level = getattr(logging, severity.upper(), logging.INFO)
    record = audit_logger.makeRecord(
        name=audit_logger.name,
        level=level,
        fn="audit",
        lno=0,
        msg=event,
        args=(),
        exc_info=None,
    )
    record.audit_extra = fields  # type: ignore[attr-defined]
    audit_logger.handle(record)


# ── HTTP middleware: logs every request with duration, status, and context ────
class AuditMiddleware(BaseHTTPMiddleware):
    """
    Logs every HTTP request as a structured JSON audit event.

    Fields logged:
      - event: "http.request"
      - method, path, query
      - status_code
      - duration_ms
      - ip (client address, respects X-Forwarded-For)
      - actor_did (extracted from JWT if present)
      - user_agent
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()

        # Extract client IP (respect proxy headers)
        forwarded_for = request.headers.get("x-forwarded-for")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (
            request.client.host if request.client else "unknown"
        )

        # Try to extract actor DID from JWT for audit context
        actor_did: Optional[str] = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from app.services.auth import decode_access_token
                token = auth_header.removeprefix("Bearer ")
                claims = decode_access_token(token)
                if claims:
                    actor_did = claims.get("sub")
            except Exception:
                pass  # Don't block on audit extraction failures

        # Store in context for downstream use
        _audit_ctx.set({
            "actor_did": actor_did,
            "ip": client_ip,
            "method": request.method,
            "path": request.url.path,
        })

        # Execute the request
        response: Optional[Response] = None
        error_detail: Optional[str] = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            error_detail = f"{type(exc).__name__}: {exc}"
            audit_event(
                "http.error",
                actor_did=actor_did,
                detail=error_detail,
                severity="ERROR",
                method=request.method,
                path=request.url.path,
                ip=client_ip,
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            status_code = response.status_code if response else 500

            # Determine severity: 4xx = WARNING, 5xx = ERROR, else INFO
            if status_code >= 500:
                severity = "ERROR"
            elif status_code >= 400:
                severity = "WARNING"
            else:
                severity = "INFO"

            # Skip noisy health checks and static assets at INFO level
            is_noisy = request.url.path in ("/health", "/favicon.ico")
            if is_noisy and severity == "INFO":
                return response  # type: ignore[return-value]

            audit_event(
                "http.request",
                actor_did=actor_did,
                severity=severity,
                method=request.method,
                path=request.url.path,
                query=str(request.query_params) if request.query_params else None,
                status_code=status_code,
                duration_ms=duration_ms,
                ip=client_ip,
                user_agent=request.headers.get("user-agent", "")[:200],
            )


def get_audit_context() -> Dict[str, Any]:
    """Retrieve the current audit context (for use in route handlers)."""
    return _audit_ctx.get()
