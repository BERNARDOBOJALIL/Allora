import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status

from app.auth_middleware import fetch_jwks, require_auth
from app.config import settings
from app.proxy_client import close_proxy_client, forward_request
from app.schemas import HealthResponse


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("api-gateway")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await fetch_jwks()
    except Exception as exc:
        logger.warning("JWKS startup load failed; will retry on protected requests: %s", exc)
    yield
    await close_proxy_client()


app = FastAPI(
    title="ALLORA API Gateway",
    lifespan=lifespan,
)


PUBLIC_AUTH_PATHS = {
    "register",
    "login",
    "refresh",
}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(service="api-gateway", status="ok")


@app.get("/me")
async def me(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return {
        "user_id": user["sub"],
        "email": user.get("email"),
        "token_payload": user,
    }


@app.api_route(
    "/auth/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def auth_proxy(path: str, request: Request):
    if path not in PUBLIC_AUTH_PATHS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ruta auth no publicada en el gateway",
        )
    return await forward_request(
        request,
        f"{settings.auth_service_url}/auth/{path}",
    )


async def protected_proxy(
    request: Request,
    service_url: str | None,
    upstream_path: str,
    user: dict[str, Any],
):
    if not service_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio no configurado",
        )
    return await forward_request(
        request,
        f"{service_url.rstrip('/')}/{upstream_path.lstrip('/')}",
        user_id=user["sub"],
    )


@app.api_route("/users", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.api_route("/users/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def users_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    return await protected_proxy(request, settings.users_service_url, path, user)


@app.api_route("/matches", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.api_route("/matches/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def matches_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    return await protected_proxy(request, settings.matches_service_url, path, user)


@app.api_route("/chat", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.api_route("/chat/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def chat_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    return await protected_proxy(request, settings.chat_service_url, path, user)


@app.api_route("/profile", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.api_route("/profile/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def profile_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    upstream_path = f"profile/{path}" if path else "profile"
    return await protected_proxy(request, settings.users_service_url, upstream_path, user)


@app.api_route("/preferences", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.api_route("/preferences/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def preferences_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    upstream_path = f"preferences/{path}" if path else "preferences"
    return await protected_proxy(request, settings.users_service_url, upstream_path, user)
