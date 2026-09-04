"""
Reusable FastAPI dependencies for JWT-based authentication and role-based
access control (RBAC).

Usage in routers:
    from app.dependencies import require_auth, require_role

    @router.get("/protected")
    async def protected(actor: AuthenticatedActor = Depends(require_auth)):
        ...

    @router.post("/admin-only")
    async def admin_only(actor: AuthenticatedActor = Depends(require_role("OEM_MANUFACTURER"))):
        ...
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, List, Optional, Set

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.actor import Actor
from app.services.auth import decode_access_token

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticatedActor:
    """Lightweight representation of the authenticated caller."""
    did: str
    role: str
    display_name: str
    is_blacklisted: bool


async def require_auth(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedActor:
    """
    FastAPI dependency that extracts and validates a JWT Bearer token from
    the Authorization header.

    Returns an `AuthenticatedActor` if the token is valid and the actor
    is not blacklisted.  Raises 401/403 otherwise.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header — send 'Bearer <jwt>'",
        )

    token = authorization.removeprefix("Bearer ")
    claims = decode_access_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired JWT token",
        )

    actor_did = claims.get("sub")
    actor_role = claims.get("role")
    if not actor_did or not actor_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT payload missing 'sub' or 'role' claims",
        )

    # Verify actor still exists and is not blacklisted
    actor = await db.get(Actor, actor_did)
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Actor {actor_did!r} no longer registered",
        )
    if actor.is_blacklisted:
        logger.warning("SECURITY: Blacklisted actor %s attempted authenticated request", actor_did)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Actor is blacklisted",
        )

    return AuthenticatedActor(
        did=actor.did,
        role=actor.role.value,
        display_name=actor.display_name,
        is_blacklisted=actor.is_blacklisted,
    )


def require_role(*allowed_roles: str) -> Callable:
    """
    Factory that returns a FastAPI dependency enforcing specific actor roles.

    Usage:
        @router.post("/sensitive", dependencies=[Depends(require_role("OEM_MANUFACTURER", "RAW_MATERIAL_SUPPLIER"))])
    or:
        @router.post("/sensitive")
        async def handler(actor: AuthenticatedActor = Depends(require_role("OEM_MANUFACTURER"))):
            ...
    """
    allowed: Set[str] = set(allowed_roles)

    async def _check(
        actor: AuthenticatedActor = Depends(require_auth),
    ) -> AuthenticatedActor:
        if actor.role not in allowed:
            logger.warning(
                "SECURITY: Actor %s (role=%s) denied — requires one of %s",
                actor.did, actor.role, allowed,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {actor.role!r} is not permitted.  Required: {sorted(allowed)}",
            )
        return actor

    return _check


def optional_auth(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[AuthenticatedActor]:
    """
    FastAPI dependency that attempts to authenticate but does NOT reject
    unauthenticated requests.  Returns None if no valid token is provided.

    Useful for endpoints that serve both public and authenticated consumers.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.removeprefix("Bearer ")
        claims = decode_access_token(token)
        if not claims:
            return None
        actor_did = claims.get("sub")
        actor_role = claims.get("role")
        if not actor_did or not actor_role:
            return None
        return AuthenticatedActor(
            did=actor_did,
            role=actor_role,
            display_name="",
            is_blacklisted=False,
        )
    except Exception:
        return None
