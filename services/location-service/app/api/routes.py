from fastapi import APIRouter, Header, HTTPException
from datetime import datetime
import httpx
from ..models import (
    HealthResponse,
    UsersResponse,
    RoomsResponse,
    CheckinRequest,
    CheckoutRequest,
    SpaceCreateRequest,
    SpaceJoinRequest,
    SpaceResponse,
    SpacesResponse,
)
from ..logger import setup_logger
from ..websocket_manager import ConnectionManager
from ..room_manager import RoomManager
from ..auth import AuthenticatedUser, resolve_authenticated_user
from ..config import settings
import math

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


def resolve_request_user(
    request_user_id: str | None,
    authorization: str | None,
    x_user_id: str | None,
) -> AuthenticatedUser:
    # Trusted identity from gateway. Gateway already validates JWT and injects X-User-Id.
    if x_user_id:
        if request_user_id and request_user_id != x_user_id:
            raise HTTPException(status_code=403, detail="El user_id no coincide con X-User-Id")
        return AuthenticatedUser(user_id=x_user_id, authenticated=True)
    return resolve_authenticated_user(request_user_id, authorization)


def cleanup_spaces_and_presence() -> None:
    deleted_spaces = room_manager.cleanup_expired_spaces()
    if not deleted_spaces:
        return
    for user_id, room_id in list(connection_manager.user_rooms.items()):
        if room_id in deleted_spaces:
            connection_manager.remove_user_from_room(user_id)


async def ensure_group_chat(space_id: str, owner_user_id: str, authorization: str | None) -> str | None:
    existing = room_manager.get_space_raw(space_id)
    if not existing:
        return None
    if existing.get("chat_conversation_id"):
        return existing.get("chat_conversation_id")

    headers = {"Content-Type": "application/json", "X-User-Id": owner_user_id}
    if authorization:
        headers["Authorization"] = authorization

    payload = {
        "group_id": space_id,
        "name": existing.get("name"),
        "description": existing.get("description"),
        "photo_base64": existing.get("photo_base64"),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.chat_service_url.rstrip('/')}/group-conversations",
            json=payload,
            headers=headers,
        )
        if response.status_code not in (200, 201):
            logger.warning("Failed creating group conversation for %s: %s", space_id, response.text)
            return None
        data = response.json()
        conversation_id = data.get("id")
        if conversation_id:
            room_manager.set_space_chat_conversation_id(space_id, conversation_id)
        return conversation_id


async def add_member_to_group_chat(
    conversation_id: str,
    user_id: str,
    authorization: str | None,
) -> None:
    headers = {"X-User-Id": user_id}
    if authorization:
        headers["Authorization"] = authorization
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"{settings.chat_service_url.rstrip('/')}/group-conversations/{conversation_id}/join",
            headers=headers,
        )


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


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
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    """Check in a user to a room."""
    try:
        cleanup_spaces_and_presence()
        authenticated_user = resolve_request_user(request.user_id, authorization, x_user_id)

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
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    """Check out a user from a room."""
    try:
        cleanup_spaces_and_presence()
        authenticated_user = resolve_request_user(request.user_id, authorization, x_user_id)

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


@router.get("/nearby")
async def get_nearby_users(lat: float, lng: float, radius_km: float = 5.0):
    """Return users within radius_km of provided lat/lng (uses current stored locations)."""
    try:
        cleanup_spaces_and_presence()
        locations = connection_manager.get_all_locations()

        results = []
        for user_id, loc in locations.items():
            try:
                d = haversine(lat, lng, float(loc.get("lat")), float(loc.get("lng")))
            except Exception:
                continue
            if d <= radius_km:
                results.append({
                    "user_id": user_id,
                    "lat": loc.get("lat"),
                    "lng": loc.get("lng"),
                    "distance_km": round(d, 3),
                    "room_id": loc.get("room_id"),
                })

        return {"count": len(results), "nearby": results}
    except Exception as e:
        logger.error(f"Nearby lookup error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/spaces", response_model=SpaceResponse, status_code=201)
async def create_space(
    request: SpaceCreateRequest,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    cleanup_spaces_and_presence()
    authenticated_user = resolve_request_user(request.user_id, authorization, x_user_id)

    space = room_manager.create_space(
        owner_user_id=authenticated_user.user_id,
        name=request.name,
        description=request.description,
        photo_base64=request.photo_base64,
        lat=request.lat,
        lng=request.lng,
        radius_km=request.radius_km,
    )

    room_manager.add_user_to_room(space["space_id"], authenticated_user.user_id)
    connection_manager.add_user_to_room(authenticated_user.user_id, space["space_id"])

    conversation_id = await ensure_group_chat(space["space_id"], authenticated_user.user_id, authorization)
    if conversation_id:
        await add_member_to_group_chat(conversation_id, authenticated_user.user_id, authorization)
        space["chat_conversation_id"] = conversation_id
    return SpaceResponse(**space)


@router.get("/spaces/nearby", response_model=SpacesResponse)
async def list_spaces_nearby(lat: float, lng: float, radius_km: float = 5.0):
    cleanup_spaces_and_presence()
    spaces = room_manager.list_spaces_nearby(lat, lng, radius_km)
    return SpacesResponse(count=len(spaces), spaces=[SpaceResponse(**space) for space in spaces])


@router.post("/spaces/{space_id}/join", response_model=SpaceResponse)
async def join_space(
    space_id: str,
    request: SpaceJoinRequest,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    cleanup_spaces_and_presence()
    authenticated_user = resolve_request_user(request.user_id, authorization, x_user_id)

    space_raw = room_manager.get_space_raw(space_id)
    if not space_raw:
        raise HTTPException(status_code=404, detail="Space no encontrado")

    location = connection_manager.get_user_location(authenticated_user.user_id)
    if not location and (request.lat is None or request.lng is None):
        raise HTTPException(
            status_code=400,
            detail="No hay ubicacion activa; envia lat/lng o conecta websocket",
        )

    user_lat = float(request.lat) if request.lat is not None else float(location.get("lat"))
    user_lng = float(request.lng) if request.lng is not None else float(location.get("lng"))

    if not room_manager.can_user_join_space(
        space_id,
        user_lat,
        user_lng,
    ):
        raise HTTPException(status_code=403, detail="No estas en proximidad del grupo")

    space = room_manager.join_space(space_id, authenticated_user.user_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space no encontrado")

    room_manager.add_user_to_room(space_id, authenticated_user.user_id)
    connection_manager.add_user_to_room(authenticated_user.user_id, space_id)
    await connection_manager.notify_user_joined(authenticated_user.user_id, space_id)

    conversation_id = space.get("chat_conversation_id") or await ensure_group_chat(
        space_id,
        space.get("owner_user_id"),
        authorization,
    )
    if conversation_id:
        await add_member_to_group_chat(conversation_id, authenticated_user.user_id, authorization)
        space["chat_conversation_id"] = conversation_id

    return SpaceResponse(**space)


@router.post("/spaces/{space_id}/leave")
async def leave_space(
    space_id: str,
    request: SpaceJoinRequest,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    cleanup_spaces_and_presence()
    authenticated_user = resolve_request_user(request.user_id, authorization, x_user_id)

    current = room_manager.get_space(space_id)
    if not current:
        raise HTTPException(status_code=404, detail="Space no encontrado")

    room_manager.remove_user_from_room(space_id, authenticated_user.user_id)
    connection_manager.remove_user_from_room(authenticated_user.user_id)
    await connection_manager.notify_user_left(authenticated_user.user_id, space_id)

    updated = room_manager.leave_space(space_id, authenticated_user.user_id)
    if updated is None:
        return {
            "status": "deleted",
            "space_id": space_id,
            "message": "Space eliminado por politica de miembros",
        }

    return {"status": "left", "space": SpaceResponse(**updated)}
