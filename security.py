from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from jose import jwt, JWTError

from app.core.config import settings


def create_access_token(*, subject: str, org_id: str, expires_minutes: Optional[int] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes or settings.access_token_minutes)
    payload: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "sub": subject,
        "org_id": org_id,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"verify_aud": False})
    except JWTError:
        return None


def get_current_user_id(token: str) -> Optional[UUID]:
    payload = decode_token(token)
    if payload is None:
        return None
    try:
        return UUID(payload["sub"])
    except (KeyError, ValueError):
        return None

