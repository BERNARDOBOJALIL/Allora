import asyncio
import os
import time

import httpx
import websockets
from jose import jwt

GATEWAY_HOST = os.getenv("GATEWAY_HOST", "127.0.0.1")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8000"))
GATEWAY_BASE = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}"
GATEWAY_WS = f"ws://{GATEWAY_HOST}:{GATEWAY_PORT}"

SECRET = os.getenv("AUTH_JWT_SECRET", "change_this_secret")
ALGO = os.getenv("AUTH_JWT_ALGORITHM", "HS256")


def create_token(sub: str = "user-test"):
    now = int(time.time())
    payload = {"sub": sub, "type": "access", "iat": now, "exp": now + 3600}
    return jwt.encode(payload, SECRET, algorithm=ALGO)


async def run():
    token = create_token("user-gateway")
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{GATEWAY_BASE}/api/v1/health")
        print("health ->", r.status_code, r.text)
        payload = {"user_id": "user-gateway", "room_id": "room1"}
        r = await client.post(f"{GATEWAY_BASE}/api/v1/checkin", json=payload, headers=headers)
        print("checkin ->", r.status_code, r.text)

    async with websockets.connect(f"{GATEWAY_WS}/ws/user-gateway?token={token}") as ws:
        for i in range(3):
            msg = {"lat": 40.0 + i * 0.001, "lng": -3.7 - i * 0.001, "timestamp": time.time()}
            await ws.send(str(msg))
            await asyncio.sleep(0.3)
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(run())
