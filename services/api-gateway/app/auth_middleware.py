import json
import logging
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidIssuerError, InvalidSignatureError, InvalidTokenError
from jwt.algorithms import RSAAlgorithm

from app.config import settings


logger = logging.getLogger("api-gateway.auth")
bearer_scheme = HTTPBearer(auto_error=False)
_public_key: Any | None = None


async def fetch_jwks() -> Any:
    global _public_key
    jwks_url = f"{settings.auth_service_url}/auth/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        jwks = response.json()

    keys = jwks.get("keys") or []
    if not keys:
        raise RuntimeError("JWKS response did not include keys")

    _public_key = RSAAlgorithm.from_jwk(json.dumps(keys[0]))
    logger.info("JWKS loaded from auth-service")
    return _public_key


async def get_public_key() -> Any:
    if _public_key is None:
        return await fetch_jwks()
    return _public_key


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    public_key = await get_public_key()
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
        )
    except InvalidSignatureError:
        public_key = await fetch_jwks()
        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=[settings.jwt_algorithm],
                issuer=settings.jwt_issuer,
            )
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalido",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (InvalidIssuerError, InvalidTokenError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload
