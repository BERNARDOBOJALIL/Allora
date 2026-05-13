#!/usr/bin/env python3
"""
Test the merged api-gateway to verify it works correctly
"""
import asyncio
import httpx
import json

GATEWAY_URL = "http://localhost:8000"


async def test_health():
    """Test gateway health endpoint"""
    print("\n=== Testing Gateway Health ===")
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{GATEWAY_URL}/health")
        print(f"GET /health")
        print(f"  Status: {r.status_code}")
        print(f"  Response: {r.json()}")
        return r.status_code == 200


async def test_auth_register():
    """Test auth register via gateway"""
    print("\n=== Testing Auth Register ===")
    async with httpx.AsyncClient() as client:
        payload = {
            "identifier": f"test{id(asyncio.current_task())}@example.com",
            "password": "TestPassword123!"
        }
        try:
            r = await client.post(
                f"{GATEWAY_URL}/auth/register",
                json=payload
            )
            print(f"POST /auth/register")
            print(f"  Status: {r.status_code}")
            print(f"  Response: {r.text[:200]}")
            return r.status_code in [200, 201, 400]  # 400 if user exists
        except Exception as e:
            print(f"  Error: {e}")
            return False


async def test_auth_login():
    """Test auth login via gateway"""
    print("\n=== Testing Auth Login ===")
    async with httpx.AsyncClient() as client:
        payload = {
            "identifier": "test@example.com",
            "password": "password123"
        }
        try:
            r = await client.post(
                f"{GATEWAY_URL}/auth/login",
                json=payload
            )
            print(f"POST /auth/login")
            print(f"  Status: {r.status_code}")
            response_text = r.text[:200]
            print(f"  Response: {response_text}")
            return r.status_code in [200, 401, 400]  # 401 if wrong credentials
        except Exception as e:
            print(f"  Error: {e}")
            return False


async def test_protected_endpoint_without_auth():
    """Test protected endpoint without auth"""
    print("\n=== Testing Protected Endpoint (No Auth) ===")
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{GATEWAY_URL}/me")
            print(f"GET /me")
            print(f"  Status: {r.status_code}")
            print(f"  Response: {r.text[:200]}")
            return r.status_code == 401
        except Exception as e:
            print(f"  Error: {e}")
            return False


async def test_users_endpoint_without_auth():
    """Test /users endpoint without auth (should fail)"""
    print("\n=== Testing /users Endpoint (No Auth) ===")
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{GATEWAY_URL}/users")
            print(f"GET /users")
            print(f"  Status: {r.status_code}")
            print(f"  Response: {r.text[:200]}")
            return r.status_code == 401
        except Exception as e:
            print(f"  Error: {e}")
            return False


async def main():
    print("=" * 60)
    print("TESTING MERGED API GATEWAY")
    print("=" * 60)
    
    results = {}
    
    try:
        results["health"] = await test_health()
        results["register"] = await test_auth_register()
        results["login"] = await test_auth_login()
        results["protected_no_auth"] = await test_protected_endpoint_without_auth()
        results["users_no_auth"] = await test_users_endpoint_without_auth()
        
        print("\n" + "=" * 60)
        print("TEST RESULTS")
        print("=" * 60)
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name:25} {status}")
        
        all_passed = all(results.values())
        print("\n" + ("✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"))
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
