import asyncio
import os
from typing import Optional

import httpx
import websockets
from fastapi import FastAPI, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

app = FastAPI(title="api-gateway")

# Use docker compose service name 'location-service' inside container network, else localhost
BACKEND_HOST = os.getenv("LOCATION_SERVICE_HOST", "location-service")
BACKEND_PORT = int(os.getenv("LOCATION_SERVICE_PORT", "8003"))
BACKEND_BASE = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
BACKEND_WS_BASE = f"ws://{BACKEND_HOST}:{BACKEND_PORT}"


@app.on_event("startup")
async def startup():
    app.state.http_client = httpx.AsyncClient(timeout=10.0)


@app.on_event("shutdown")
async def shutdown():
    await app.state.http_client.aclose()


async def proxy_request(path: str, request: Request, token: Optional[str] = None):
    url = f"{BACKEND_BASE}{path}"
    headers = {k: v for k, v in request.headers.items()}
    if token:
        headers["authorization"] = f"Bearer {token}"
    data = await request.body()
    resp = await app.state.http_client.request(request.method, url, content=data, headers=headers)
    return JSONResponse(status_code=resp.status_code, content=resp.json())


@app.get("/api/v1/health")
async def health(request: Request):
    return await proxy_request("/api/v1/health", request)


@app.get("/api/v1/users")
async def users(request: Request):
    return await proxy_request("/api/v1/users", request)


@app.get("/api/v1/rooms")
async def rooms(request: Request):
    return await proxy_request("/api/v1/rooms", request)


@app.post("/api/v1/checkin")
async def checkin(request: Request, authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    return await proxy_request("/api/v1/checkin", request, token=token)


@app.post("/api/v1/checkout")
async def checkout(request: Request, authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    return await proxy_request("/api/v1/checkout", request, token=token)


async def relay_websocket(client_ws: WebSocket, backend_ws_uri: str):
    await client_ws.accept()
    async with websockets.connect(backend_ws_uri) as backend_ws:
        async def client_to_backend():
            try:
                while True:
                    msg = await client_ws.receive_text()
                    await backend_ws.send(msg)
            except WebSocketDisconnect:
                await backend_ws.close()
            except Exception:
                try:
                    await backend_ws.close()
                except Exception:
                    pass

        async def backend_to_client():
            try:
                async for message in backend_ws:
                    await client_ws.send_text(message)
            except Exception:
                try:
                    await client_ws.close()
                except Exception:
                    pass

        tasks = [asyncio.create_task(client_to_backend()), asyncio.create_task(backend_to_client())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()


@app.websocket("/ws/{user_id}")
async def websocket_gateway(websocket: WebSocket, user_id: str, token: Optional[str] = None):
    # token can be passed as query param or via Authorization header on initial HTTP upgrade
    auth_token = token
    # If not in query param, try to read headers from the scope
    if not auth_token:
        headers = dict(websocket.scope.get("headers", []))
        auth = headers.get(b"authorization")
        if auth:
            try:
                auth_str = auth.decode()
                if auth_str.lower().startswith("bearer "):
                    auth_token = auth_str.split(" ", 1)[1]
            except Exception:
                pass
    backend_uri = f"{BACKEND_WS_BASE}/ws/{user_id}"
    if auth_token:
        backend_uri = f"{backend_uri}?token={auth_token}"
    await relay_websocket(websocket, backend_uri)
