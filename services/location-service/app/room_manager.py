from typing import Dict, List
from .logger import setup_logger

logger = setup_logger(__name__)


class RoomManager:
    """Manages virtual rooms and user presence."""

    def __init__(self):
        self.rooms: Dict[str, List[str]] = {}

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
