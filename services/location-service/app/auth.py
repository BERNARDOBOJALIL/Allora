from dataclasses import dataclass

from fastapi import HTTPException, status
from jose import JWTError, jwt

from .config import settings


@dataclass(slots=True)
class AuthenticatedUser:
    user_id: str
    role: str | None = None
    plan: str | None = None
    nombre: str | None = None
    authenticated: bool = False


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.auth_jwt_secret,
            algorithms=[settings.auth_jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
        ) from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
        )

    return payload


def resolve_authenticated_user(
    user_id: str | None,
    authorization: str | None,
) -> AuthenticatedUser:
    token = extract_bearer_token(authorization)
    if not token:
        if user_id:
            return AuthenticatedUser(user_id=user_id, authenticated=False)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere Authorization Bearer o user_id",
        )

    payload = decode_access_token(token)
    token_user_id = str(payload["sub"])

    if user_id and user_id != token_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El user_id no coincide con el token",
        )

    return AuthenticatedUser(
        user_id=token_user_id,
        role=payload.get("role"),
        plan=payload.get("plan"),
        nombre=payload.get("nombre") or payload.get("name"),
        authenticated=True,
    )