#!/usr/bin/env python3
"""
WebSocket test client for location-service.

This script demonstrates how to connect to the location-service WebSocket endpoint
and send location updates.
"""

import asyncio
import json
import websockets
from datetime import datetime
import random


async def test_user(user_id: str, room_id: str, num_updates: int = 5):
    """
    Test a single user's WebSocket connection.

    Args:
        user_id: Unique user identifier
        room_id: Room to join
        num_updates: Number of location updates to send
    """
    uri = f"ws://localhost:8003/ws/{user_id}"

    try:
        async with websockets.connect(uri) as websocket:
            print(f"\n[{user_id}] Connected to WebSocket")

            # Send location updates
            for i in range(num_updates):
                # Generate random location (simulating movement)
                lat = 40.7128 + random.uniform(-0.05, 0.05)
                lng = -74.0060 + random.uniform(-0.05, 0.05)

                message = {
                    "lat": lat,
                    "lng": lng,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                await websocket.send(json.dumps(message))
                print(f"[{user_id}] Sent location update {i+1}: {message}")

                # Listen for broadcasted messages (non-blocking)
                try:
                    response = await asyncio.wait_for(
                        websocket.recv(), timeout=1.0
                    )
                    print(f"[{user_id}] Received: {response}")
                except asyncio.TimeoutError:
                    pass

                # Wait before next update
                await asyncio.sleep(2)

            print(f"[{user_id}] Completed location updates")

    except Exception as e:
        print(f"[{user_id}] Error: {e}")


async def test_rest_endpoints():
    """Test REST endpoints."""
    import httpx

    base_url = "http://localhost:8003/api/v1"

    async with httpx.AsyncClient() as client:
        print("\n=== Testing REST Endpoints ===\n")

        # Health check
        print("GET /health")
        response = await client.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")

        # Get users
        print("GET /users")
        response = await client.get(f"{base_url}/users")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")

        # Get rooms
        print("GET /rooms")
        response = await client.get(f"{base_url}/rooms")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")

        # Check in user
        print("POST /checkin")
        response = await client.post(
            f"{base_url}/checkin",
            json={"user_id": "user1", "room_id": "room1"},
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")

        # Check out user
        print("POST /checkout")
        response = await client.post(
            f"{base_url}/checkout",
            json={"user_id": "user1", "room_id": "room1"},
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")


async def main():
    """Main test function."""
    print("=" * 60)
    print("Location Service - WebSocket Test Client")
    print("=" * 60)

    # Test REST endpoints
    try:
        await test_rest_endpoints()
    except Exception as e:
        print(f"REST endpoints test error: {e}")
        print(
            "Make sure the service is running: python main.py\n"
        )

    # Simulate multiple users connecting and sending location updates
    print("\n=== Testing WebSocket Connections ===\n")

    tasks = []

    # Create 3 users in the same room
    for i in range(1, 4):
        user_id = f"user{i}"
        room_id = "room1"
        task = test_user(user_id, room_id, num_updates=3)
        tasks.append(task)

    # Run all user tasks concurrently
    await asyncio.gather(*tasks)

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
