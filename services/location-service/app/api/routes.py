from fastapi import APIRouter, Header, HTTPException
from datetime import datetime
from ..models import (
    HealthResponse,
    UsersResponse,
    RoomsResponse,
    CheckinRequest,
    CheckoutRequest,
)
from ..logger import setup_logger
from ..websocket_manager import ConnectionManager
from ..room_manager import RoomManager
from ..auth import resolve_authenticated_user

router = APIRouter()
logger = setup_logger(__name__)

# These will be injected from main.py
connection_manager: ConnectionManager = None
room_manager: RoomManager = None


def init_routes(conn_manager: ConnectionManager, room_mgr: RoomManager):
    """Initialize route managers."""
    global connection_manager, room_manager
    connection_manager = conn_manager
    room_manager = room_mgr


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return HealthResponse(
        status="healthy",
        service="location-service",
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/users", response_model=UsersResponse)
async def get_connected_users():
    """Get list of connected users."""
    users = connection_manager.get_connected_users()
    logger.info(f"Fetched {len(users)} connected users")
    return UsersResponse(connected_users=len(users), users=users)


@router.get("/rooms", response_model=RoomsResponse)
async def get_active_rooms():
    """Get active rooms and their users."""
    rooms = room_manager.get_all_rooms()
    logger.info(f"Fetched {len(rooms)} active rooms")
    return RoomsResponse(active_rooms=len(rooms), rooms=rooms)


@router.post("/checkin")
async def checkin(
    request: CheckinRequest,
    authorization: str | None = Header(default=None),
):
    """Check in a user to a room."""
    try:
        authenticated_user = resolve_authenticated_user(request.user_id, authorization)

        # Add user to room via room manager
        room_manager.add_user_to_room(request.room_id, authenticated_user.user_id)

        # Add user to room via connection manager
        connection_manager.add_user_to_room(authenticated_user.user_id, request.room_id)

        # Notify other users in the room
        await connection_manager.notify_user_joined(authenticated_user.user_id, request.room_id)

        logger.info(
            f"User {authenticated_user.user_id} checked in to room {request.room_id}"
        )

        return {
            "status": "success",
            "message": f"User {authenticated_user.user_id} checked in to room {request.room_id}",
            "timestamp": datetime.utcnow().isoformat(),
            "authenticated": authenticated_user.authenticated,
        }
    except Exception as e:
        logger.error(f"Check-in error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/checkout")
async def checkout(
    request: CheckoutRequest,
    authorization: str | None = Header(default=None),
):
    """Check out a user from a room."""
    try:
        authenticated_user = resolve_authenticated_user(request.user_id, authorization)

        # Remove user from room via room manager
        room_manager.remove_user_from_room(request.room_id, authenticated_user.user_id)

        # Remove user from room via connection manager
        connection_manager.remove_user_from_room(authenticated_user.user_id)

        # Notify other users in the room
        await connection_manager.notify_user_left(authenticated_user.user_id, request.room_id)

        logger.info(
            f"User {authenticated_user.user_id} checked out from room {request.room_id}"
        )

        return {
            "status": "success",
            "message": f"User {authenticated_user.user_id} checked out from room {request.room_id}",
            "timestamp": datetime.utcnow().isoformat(),
            "authenticated": authenticated_user.authenticated,
        }
    except Exception as e:
        logger.error(f"Check-out error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
