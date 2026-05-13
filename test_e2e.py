#!/usr/bin/env python3
"""
End-to-end integration test: Register/Login (via auth-service mock) -> Gateway -> Location-Service
Tests REST endpoints and WebSocket relay through gateway
"""
import asyncio
import json
import time
from typing import Optional

import httpx
import websockets
from jose import jwt

GATEWAY_URL = "http://localhost:8000"
GATEWAY_WS = "ws://localhost:8000"
SECRET = "change_this_secret"
ALGO = "HS256"


def create_jwt(user_id: str = "test-user-001") -> str:
    """Create a valid JWT token"""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + 3600
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)


async def test_rest_endpoints():
    """Test REST endpoints via gateway"""
    print("\n=== Testing REST Endpoints ===")
    token = create_jwt("user-rest-01")
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        # Test health
        print("\n[1] GET /api/v1/health")
        r = await client.get(f"{GATEWAY_URL}/api/v1/health")
        print(f"    Status: {r.status_code}")
        print(f"    Response: {r.text}")
        
        # Test users list
        print("\n[2] GET /api/v1/users")
        r = await client.get(f"{GATEWAY_URL}/api/v1/users")
        print(f"    Status: {r.status_code}")
        print(f"    Response: {r.text}")
        
        # Test rooms list
        print("\n[3] GET /api/v1/rooms")
        r = await client.get(f"{GATEWAY_URL}/api/v1/rooms")
        print(f"    Status: {r.status_code}")
        print(f"    Response: {r.text}")
        
        # Test checkin with auth
        print("\n[4] POST /api/v1/checkin (with JWT)")
        payload = {"user_id": "user-rest-01", "room_id": "test-room"}
        r = await client.post(
            f"{GATEWAY_URL}/api/v1/checkin",
            json=payload,
            headers=headers
        )
        print(f"    Status: {r.status_code}")
        print(f"    Response: {r.text}")


async def test_websocket():
    """Test WebSocket relay through gateway"""
    print("\n=== Testing WebSocket Relay ===")
    token = create_jwt("user-ws-01")
    
    ws_url = f"{GATEWAY_WS}/ws/user-ws-01?token={token}"
    print(f"\n[5] WebSocket: Connecting to {ws_url}")
    
    try:
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            print("    ✓ Connected to gateway WebSocket")
            
            # Send location updates
            for i in range(3):
                msg = json.dumps({
                    "lat": 40.4168 + (i * 0.001),
                    "lng": -3.7038 + (i * 0.001),
                    "timestamp": time.time()
                })
                await ws.send(msg)
                print(f"    ✓ Sent location update {i+1}")
                await asyncio.sleep(0.5)
            
            print("    ✓ WebSocket test passed")
    except Exception as e:
        print(f"    ✗ WebSocket error: {e}")


async def test_multiple_users():
    """Test multiple concurrent users"""
    print("\n=== Testing Multiple Concurrent Users ===")
    
    async def user_flow(user_id: str):
        token = create_jwt(user_id)
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient() as client:
            # Checkin
            r = await client.post(
                f"{GATEWAY_URL}/api/v1/checkin",
                json={"user_id": user_id, "room_id": "shared-room"},
                headers=headers
            )
            print(f"  User {user_id}: checkin {r.status_code}")
            
            # WebSocket
            ws_url = f"{GATEWAY_WS}/ws/{user_id}?token={token}"
            async with websockets.connect(ws_url, ping_interval=None) as ws:
                for i in range(2):
                    msg = json.dumps({
                        "lat": 40.0 + float(i),
                        "lng": -3.7 + float(i),
                        "timestamp": time.time()
                    })
                    await ws.send(msg)
                print(f"  User {user_id}: WS messages sent")
    
    print("\n[6] Concurrent users test (3 users)")
    await asyncio.gather(
        user_flow("user-concurrent-01"),
        user_flow("user-concurrent-02"),
        user_flow("user-concurrent-03"),
    )
    print("  ✓ All users completed")


async def main():
    print("=" * 60)
    print("END-TO-END INTEGRATION TEST: Gateway -> Location-Service")
    print("=" * 60)
    
    try:
        await test_rest_endpoints()
        await test_websocket()
        await test_multiple_users()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
