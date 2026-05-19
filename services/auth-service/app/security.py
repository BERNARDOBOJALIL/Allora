import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.models import utc_now


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_private_key_pem: str | None = None
_public_key_pem: str | None = None


def _base64url_uint(value: int) -> str:
    import base64

    byte_length = (value.bit_length() + 7) // 8
    data = value.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _generate_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def get_signing_keys() -> tuple[str, str]:
    global _private_key_pem, _public_key_pem
    if _private_key_pem and _public_key_pem:
        return _private_key_pem, _public_key_pem

    if settings.jwt_private_key and settings.jwt_public_key:
        _private_key_pem = settings.jwt_private_key.replace("\\n", "\n")
        _public_key_pem = settings.jwt_public_key.replace("\\n", "\n")
    else:
        _private_key_pem, _public_key_pem = _generate_key_pair()
    return _private_key_pem, _public_key_pem


def get_jwks() -> dict[str, list[dict[str, str]]]:
    _, public_key_pem = get_signing_keys()
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    numbers = public_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "kid": settings.jwt_key_id,
                "alg": "RS256",
                "n": _base64url_uint(numbers.n),
                "e": _base64url_uint(numbers.e),
            }
        ]
    }


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


def create_access_token(
    user_id: str,
    role: str,
    plan: str,
    email: str | None = None,
    nombre: str | None = None,
) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.jwt_expire_minutes)
    now = utc_now()
    expires_at = now + expires_delta
    payload = {
        "sub": user_id,
        "type": "access",
        "role": role,
        "plan": plan,
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": expires_at,
    }
    if email:
        payload["email"] = email
    if nombre:
        payload["nombre"] = nombre
    if settings.jwt_algorithm == "RS256":
        private_key_pem, _ = get_signing_keys()
        token = jwt.encode(
            payload,
            private_key_pem,
            algorithm=settings.jwt_algorithm,
            headers={"kid": settings.jwt_key_id},
        )
    else:
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        key = settings.jwt_secret
        if settings.jwt_algorithm == "RS256":
            _, key = get_signing_keys()
        payload = jwt.decode(
            token,
            key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
        )
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise ValueError("Invalid token")
    return payload
