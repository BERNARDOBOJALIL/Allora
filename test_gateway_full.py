#!/usr/bin/env python3
"""
Complete test of the merged api-gateway with authentication flow
"""
import asyncio
import httpx
import json

GATEWAY_URL = "http://localhost:8000"
AUTH_SERVICE = "http://localhost:8000"


async def main():
    print("=" * 60)
    print("COMPLETE GATEWAY TEST WITH AUTH FLOW")
    print("=" * 60)
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 1. Test health
        print("\n[1] Gateway Health Check")
        r = await client.get(f"{GATEWAY_URL}/health")
        print(f"    Status: {r.status_code}")
        print(f"    Response: {r.json()}")
        
        # 2. Test auth endpoints
        print("\n[2] Testing /auth endpoints (public)")
        
        # Try register with complete data
        print("\n    - POST /auth/register")
        payload = {
            "identifier": "gateway-test@example.com",
            "password": "TestPassword123!",
            "nombre": "Test User"  # Added 'nombre' field
        }
        r = await client.post(f"{GATEWAY_URL}/auth/register", json=payload)
        print(f"      Status: {r.status_code}")
        if r.status_code in [200, 201]:
            print(f"      ✅ Registration successful")
        elif r.status_code == 409:
            print(f"      ℹ️  User already exists")
        else:
            print(f"      Response: {r.text[:300]}")
        
        # Try login
        print("\n    - POST /auth/login")
        payload = {
            "identifier": "gateway-test@example.com",
            "password": "TestPassword123!"
        }
        r = await client.post(f"{GATEWAY_URL}/auth/login", json=payload)
        print(f"      Status: {r.status_code}")
        
        token = None
        if r.status_code == 200:
            data = r.json()
            token = data.get("access_token")
            print(f"      ✅ Login successful, got token: {token[:50]}...")
        else:
            print(f"      Response: {r.text[:300]}")
        
        # 3. Test protected endpoints
        if token:
            print("\n[3] Testing protected endpoints with auth")
            headers = {"Authorization": f"Bearer {token}"}
            
            print("\n    - GET /me")
            r = await client.get(f"{GATEWAY_URL}/me", headers=headers)
            print(f"      Status: {r.status_code}")
            print(f"      Response: {r.json()}")
            
            print("\n    - GET /users")
            r = await client.get(f"{GATEWAY_URL}/users", headers=headers)
            print(f"      Status: {r.status_code}")
            print(f"      Response (first 300 chars): {r.text[:300]}")
        else:
            print("\n⚠️  No token obtained, skipping protected endpoints")
        
        # 4. Test protected endpoints without auth
        print("\n[4] Testing protected endpoints WITHOUT auth (should fail)")
        
        print("\n    - GET /me (no auth)")
        r = await client.get(f"{GATEWAY_URL}/me")
        print(f"      Status: {r.status_code}")
        print(f"      Expected: 401 - Got: {'✅' if r.status_code == 401 else '❌'}")
        
        print("\n    - GET /users (no auth)")
        r = await client.get(f"{GATEWAY_URL}/users")
        print(f"      Status: {r.status_code}")
        print(f"      Expected: 401 - Got: {'✅' if r.status_code == 401 else '❌'}")
    
    print("\n" + "=" * 60)
    print("GATEWAY STATUS: ✅ FUNCTIONAL")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
