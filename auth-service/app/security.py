import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.models import utc_now


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    normalized = email.strip().lower()
    return normalized or None


def normalize_phone(telefono: str | None) -> str | None:
    if telefono is None:
        return None
    normalized = telefono.strip()
    return normalized or None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(password, password_hash)


def hash_secret(value: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_secret(value: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(value), stored_hash)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def generate_verification_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def create_access_token(user_id: str, role: str, plan: str) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.jwt_expire_minutes)
    now = utc_now()
    expires_at = now + expires_delta
    payload = {
        "sub": user_id,
        "type": "access",
        "role": role,
        "plan": plan,
        "iat": int(now.timestamp()),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), int(
        expires_delta.total_seconds()
    )


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise ValueError("Invalid token")
    return payload
