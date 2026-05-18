from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import math
import uuid
from .logger import setup_logger

logger = setup_logger(__name__)


class RoomManager:
    """Manages virtual rooms and user presence."""

    def __init__(self):
        self.rooms: Dict[str, List[str]] = {}
        self.spaces: Dict[str, dict[str, Any]] = {}

    def create_room(self, room_id: str) -> bool:
        """Create a new room."""
        if room_id not in self.rooms:
            self.rooms[room_id] = []
            logger.info(f"Room {room_id} created")
            return True
        return False

    def add_user_to_room(self, room_id: str, user_id: str) -> bool:
        """Add user to room (creates room if doesn't exist)."""
        if room_id not in self.rooms:
            self.create_room(room_id)

        if user_id not in self.rooms[room_id]:
            self.rooms[room_id].append(user_id)
            logger.info(f"User {user_id} added to room {room_id}")
            return True
        return False

    def remove_user_from_room(self, room_id: str, user_id: str) -> bool:
        """Remove user from room."""
        if room_id in self.rooms and user_id in self.rooms[room_id]:
            self.rooms[room_id].remove(user_id)
            logger.info(f"User {user_id} removed from room {room_id}")

            # Delete room if empty
            if not self.rooms[room_id]:
                del self.rooms[room_id]
                logger.info(f"Room {room_id} deleted (empty)")

            return True
        return False

    def get_room_users(self, room_id: str) -> List[str]:
        """Get all users in a room."""
        return self.rooms.get(room_id, []).copy()

    def get_all_rooms(self) -> Dict[str, List[str]]:
        """Get all rooms and their users."""
        return {room_id: users.copy() for room_id, users in self.rooms.items()}

    def room_exists(self, room_id: str) -> bool:
        """Check if a room exists."""
        return room_id in self.rooms

    def get_active_rooms_count(self) -> int:
        """Get number of active rooms."""
        return len(self.rooms)

    def get_total_users_in_rooms(self) -> int:
        """Get total number of users across all rooms."""
        return sum(len(users) for users in self.rooms.values())

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius_km = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius_km * c

    def create_space(
        self,
        owner_user_id: str,
        name: str,
        description: str,
        photo_base64: str,
        lat: float,
        lng: float,
        radius_km: float,
    ) -> dict[str, Any]:
        space_id = f"space-{uuid.uuid4().hex[:12]}"
        now = self._utc_now()
        expires_at = now + timedelta(hours=1)
        self.spaces[space_id] = {
            "space_id": space_id,
            "name": name.strip(),
            "description": description.strip(),
            "photo_base64": photo_base64,
            "owner_user_id": owner_user_id,
            "lat": lat,
            "lng": lng,
            "radius_km": radius_km,
            "members": [owner_user_id],
            "joined_count": 1,
            "chat_conversation_id": None,
            "created_at": now,
            "expires_at": expires_at,
        }
        logger.info("Space %s created by %s", space_id, owner_user_id)
        return self.get_space(space_id)

    def get_space(self, space_id: str) -> dict[str, Any] | None:
        space = self.spaces.get(space_id)
        if not space:
            return None
        return self._serialize_space(space)

    def get_space_raw(self, space_id: str) -> dict[str, Any] | None:
        return self.spaces.get(space_id)

    def set_space_chat_conversation_id(self, space_id: str, conversation_id: str) -> None:
        if space_id in self.spaces:
            self.spaces[space_id]["chat_conversation_id"] = conversation_id

    def join_space(self, space_id: str, user_id: str) -> dict[str, Any] | None:
        space = self.spaces.get(space_id)
        if not space:
            return None
        if user_id not in space["members"]:
            space["members"].append(user_id)
            space["joined_count"] += 1
            logger.info("User %s joined space %s", user_id, space_id)
        return self._serialize_space(space)

    def leave_space(self, space_id: str, user_id: str) -> dict[str, Any] | None:
        space = self.spaces.get(space_id)
        if not space:
            return None
        if user_id in space["members"]:
            space["members"].remove(user_id)
            logger.info("User %s left space %s", user_id, space_id)
        if len(space["members"]) <= 1 and space.get("joined_count", 1) > 1:
            del self.spaces[space_id]
            logger.info("Space %s deleted because it has <= 1 member", space_id)
            return None
        return self._serialize_space(space)

    def list_spaces_nearby(self, lat: float, lng: float, radius_km: float) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for space in self.spaces.values():
            distance = self._haversine(lat, lng, float(space["lat"]), float(space["lng"]))
            if distance <= radius_km:
                serialized = self._serialize_space(space)
                serialized["distance_km"] = round(distance, 3)
                results.append(serialized)
        return results

    def can_user_join_space(self, space_id: str, user_lat: float, user_lng: float) -> bool:
        space = self.spaces.get(space_id)
        if not space:
            return False
        distance = self._haversine(user_lat, user_lng, float(space["lat"]), float(space["lng"]))
        return distance <= float(space["radius_km"])

    def cleanup_expired_spaces(self) -> list[str]:
        now = self._utc_now()
        to_delete: list[str] = []
        for space_id, space in self.spaces.items():
            # If nobody joined after creator in 1h, remove the space.
            if space.get("joined_count", 1) <= 1 and now >= space["expires_at"]:
                to_delete.append(space_id)
                continue
            # If only one person remains after having had more than one member, remove immediately.
            if len(space.get("members", [])) <= 1 and space.get("joined_count", 1) > 1:
                to_delete.append(space_id)

        for space_id in to_delete:
            self.spaces.pop(space_id, None)
            logger.info("Space %s removed by cleanup policy", space_id)
        return to_delete

    @staticmethod
    def _serialize_space(space: dict[str, Any]) -> dict[str, Any]:
        return {
            "space_id": space["space_id"],
            "name": space["name"],
            "description": space["description"],
            "photo_base64": space["photo_base64"],
            "owner_user_id": space["owner_user_id"],
            "lat": space["lat"],
            "lng": space["lng"],
            "radius_km": space["radius_km"],
            "members": list(space.get("members", [])),
            "chat_conversation_id": space.get("chat_conversation_id"),
            "created_at": space["created_at"].isoformat(),
            "expires_at": space.get("expires_at").isoformat() if space.get("expires_at") else None,
        }
