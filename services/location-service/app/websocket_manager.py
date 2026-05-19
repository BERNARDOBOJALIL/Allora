import json
from fastapi import WebSocket
from typing import Dict, List, Set
from .logger import setup_logger
from .models import LocationUpdate

logger = setup_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and location broadcasting."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_locations: Dict[str, dict] = {}
        self.user_rooms: Dict[str, str] = {}  # user_id -> room_id
        self.user_names: Dict[str, str] = {}

    async def connect(self, user_id: str, websocket: WebSocket, user_name: str | None = None):
        """Register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        if user_name:
            self.user_names[user_id] = user_name
        logger.info(f"User {user_id} connected. Total connections: {len(self.active_connections)}")

    async def disconnect(self, user_id: str):
        """Remove a disconnected user."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]

        if user_id in self.user_locations:
            del self.user_locations[user_id]

        if user_id in self.user_rooms:
            room_id = self.user_rooms[user_id]
            del self.user_rooms[user_id]
            logger.info(f"User {user_id} disconnected from room {room_id}")
        else:
            logger.info(f"User {user_id} disconnected")

        if user_id in self.user_names:
            del self.user_names[user_id]

    async def broadcast_location(self, user_id: str, location_data: dict):
        """Broadcast location update to all connected users regardless of rooms."""
        sender_room_id = self.user_rooms.get(user_id)

        broadcast_data = {
            "type": "location_update",
            "user_id": user_id,
            "user_name": self.user_names.get(user_id),
            "data": location_data,
            "room_id": sender_room_id,
        }

        for other_user in list(self.active_connections.keys()):
            if other_user in self.active_connections:
                try:
                    await self.active_connections[other_user].send_json(broadcast_data)
                except Exception as e:
                    logger.error(f"Error broadcasting to {other_user}: {str(e)}")

    async def send_personal_message(self, user_id: str, data: dict):
        """Send a message to a specific user."""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(data)
            except Exception as e:
                logger.error(f"Error sending message to {user_id}: {str(e)}")

    async def notify_user_joined(self, user_id: str, room_id: str):
        """Notify all users in a room that a user joined."""
        users_in_room = [uid for uid, rid in self.user_rooms.items() if rid == room_id]

        notification = {
            "type": "user_joined",
            "user_id": user_id,
            "room_id": room_id,
            "users_in_room": users_in_room,
        }

        for other_user in users_in_room:
            if other_user in self.active_connections:
                try:
                    await self.active_connections[other_user].send_json(notification)
                except Exception as e:
                    logger.error(f"Error notifying {other_user}: {str(e)}")

    async def notify_user_left(self, user_id: str, room_id: str):
        """Notify all users in a room that a user left."""
        users_in_room = [uid for uid, rid in self.user_rooms.items() if rid == room_id]

        notification = {
            "type": "user_left",
            "user_id": user_id,
            "room_id": room_id,
            "users_in_room": users_in_room,
        }

        for other_user in users_in_room:
            if other_user in self.active_connections:
                try:
                    await self.active_connections[other_user].send_json(notification)
                except Exception as e:
                    logger.error(f"Error notifying {other_user}: {str(e)}")

    def get_connected_users(self) -> List[str]:
        """Get list of connected users."""
        return list(self.active_connections.keys())

    def get_user_location(self, user_id: str) -> dict:
        """Get location of a specific user."""
        return self.user_locations.get(user_id, {})

    def get_all_locations(self) -> dict:
        """Get all user locations."""
        return self.user_locations.copy()

    def get_user_name(self, user_id: str) -> str | None:
        """Get display name of a connected/authenticated user."""
        return self.user_names.get(user_id)

    def set_user_name(self, user_id: str, user_name: str | None) -> None:
        """Store or update display name for a connected user."""
        cleaned = (user_name or "").strip()
        if cleaned:
            self.user_names[user_id] = cleaned

    def store_location(self, user_id: str, location: dict):
        """Store user location."""
        self.set_user_name(
            user_id,
            location.get("user_name") or location.get("nombre") or location.get("name"),
        )
        if "room_id" not in location:
            location["room_id"] = self.user_rooms.get(user_id)
        self.user_locations[user_id] = location

    def add_user_to_room(self, user_id: str, room_id: str):
        """Add user to a room."""
        self.user_rooms[user_id] = room_id
        if user_id in self.user_locations:
            self.user_locations[user_id]["room_id"] = room_id

    def remove_user_from_room(self, user_id: str) -> str:
        """Remove user from their room."""
        previous_room = self.user_rooms.pop(user_id, None)
        if user_id in self.user_locations:
            self.user_locations[user_id]["room_id"] = None
        return previous_room

    def get_room_users(self, room_id: str) -> List[str]:
        """Get all users in a specific room."""
        return [uid for uid, rid in self.user_rooms.items() if rid == room_id]

    def get_user_room(self, user_id: str) -> str:
        """Get the room a user is in."""
        return self.user_rooms.get(user_id)

    def get_all_rooms(self) -> Dict[str, List[str]]:
        """Get all rooms and their users."""
        rooms = {}
        for user_id, room_id in self.user_rooms.items():
            if room_id not in rooms:
                rooms[room_id] = []
            rooms[room_id].append(user_id)
        return rooms
