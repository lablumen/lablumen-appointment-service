"""Cognito JWT verification (in-process) + lazy user provisioning.

There is no separate auth-service: Cognito issues tokens, each service verifies them here using
the pool's published JWKS (cached by PyJWKClient), and roles are read from the `cognito:groups`
claim. On first authenticated request a `users` row is upserted from the token claims.
"""

from dataclasses import dataclass, field

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_session

_issuer = (
    f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_user_pool_id}"
)
# PyJWKClient fetches lazily on first use, so an unset/placeholder pool id won't break import.
_jwk_client = PyJWKClient(f"{_issuer}/.well-known/jwks.json")
_bearer = HTTPBearer(auto_error=True)


@dataclass
class CurrentUser:
    sub: str
    email: str | None
    groups: list[str] = field(default_factory=list)


async def _ensure_user(session: AsyncSession, user: CurrentUser) -> None:
    await session.execute(
        text(
            "INSERT INTO users (user_id, email) VALUES (CAST(:sub AS uuid), :email) "
            "ON CONFLICT (user_id) DO NOTHING"
        ),
        {"sub": user.sub, "email": user.email},
    )
    await session.commit()


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    token = creds.credentials
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=_issuer,
            options={"verify_aud": False},  # Cognito access tokens carry client_id, not aud
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}"
        ) from exc

    user = CurrentUser(
        sub=claims["sub"],
        email=claims.get("email"),
        groups=claims.get("cognito:groups", []) or [],
    )
    await _ensure_user(session, user)
    return user


def require_roles(*roles: str):
    """Dependency factory enforcing membership in at least one Cognito group."""

    async def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not set(roles).intersection(user.groups):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return user

    return _checker
