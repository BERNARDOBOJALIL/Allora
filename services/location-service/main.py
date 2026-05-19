import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, Header, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import ValidationError

from app.config import settings
from app.logger import setup_logger
from app.websocket_manager import ConnectionManager
from app.room_manager import RoomManager
from app.models import LocationUpdate
from app.api.routes import init_routes, router
from app.auth import resolve_authenticated_user, extract_bearer_token

logger = setup_logger(__name__, settings.log_level)

# Global managers
connection_manager = ConnectionManager()
room_manager = RoomManager()


def normalize_location_payload(message: dict) -> dict:
    """Accept common frontend payload shapes for location updates."""
    if "lat" in message and "lng" in message:
        normalized = dict(message)
    elif "latitude" in message and "longitude" in message:
        normalized = {
            "lat": message.get("latitude"),
            "lng": message.get("longitude"),
            "timestamp": message.get("timestamp"),
            "user_name": message.get("user_name") or message.get("nombre") or message.get("name"),
        }
    elif isinstance(message.get("data"), dict):
        return normalize_location_payload(message["data"])
    else:
        raise ValueError("Invalid location payload. Expected lat/lng or latitude/longitude")

    if normalized.get("timestamp") is None:
        normalized["timestamp"] = datetime.utcnow().isoformat()

    return normalized


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info(f"Starting {settings.service_name}")
    stop_event = asyncio.Event()

    async def cleanup_spaces_task():
        while not stop_event.is_set():
            deleted_spaces = room_manager.cleanup_expired_spaces()
            if deleted_spaces:
                for user_id, room_id in list(connection_manager.user_rooms.items()):
                    if room_id in deleted_spaces:
                        connection_manager.remove_user_from_room(user_id)
            await asyncio.sleep(60)

    cleanup_task = asyncio.create_task(cleanup_spaces_task())
    yield
    stop_event.set()
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info(f"Shutting down {settings.service_name}")


# Create FastAPI app
app = FastAPI(
    title=settings.service_name,
    version="1.0.0",
    description="Real-time location and presence tracking service",
    lifespan=lifespan,
)

# Initialize routes with managers
init_routes(connection_manager, room_manager)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["location"])


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
):
    """WebSocket endpoint for real-time location updates."""
    authenticated_user = None
    try:
        bearer_token = token or extract_bearer_token(authorization)
        authenticated_user = resolve_authenticated_user(
            user_id,
            f"Bearer {bearer_token}" if bearer_token else None,
        )

        await connection_manager.connect(
            authenticated_user.user_id,
            websocket,
            user_name=authenticated_user.nombre,
        )
        logger.info(
            f"WebSocket connection established for user {authenticated_user.user_id}"
        )

        while True:
            try:
                # Receive JSON message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                normalized_message = normalize_location_payload(message)

                # Validate location update
                location_update = LocationUpdate(**normalized_message)

                reported_user_name = (
                    normalized_message.get("user_name")
                    or normalized_message.get("nombre")
                    or normalized_message.get("name")
                )
                if reported_user_name:
                    connection_manager.set_user_name(
                        authenticated_user.user_id,
                        str(reported_user_name),
                    )

                current_room_id = connection_manager.get_user_room(authenticated_user.user_id)

                # Store location
                connection_manager.store_location(
                    authenticated_user.user_id,
                    {
                        "lat": location_update.lat,
                        "lng": location_update.lng,
                        "timestamp": location_update.timestamp,
                        "room_id": current_room_id,
                        "user_name": reported_user_name,
                    },
                )

                # Broadcast to users in same room
                await connection_manager.broadcast_location(
                    authenticated_user.user_id,
                    {
                        "lat": location_update.lat,
                        "lng": location_update.lng,
                        "timestamp": location_update.timestamp,
                    },
                )

                logger.info(
                    f"Location update from {authenticated_user.user_id}: lat={location_update.lat}, lng={location_update.lng}"
                )

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from {authenticated_user.user_id}: {str(e)}")
                await connection_manager.send_personal_message(
                    authenticated_user.user_id,
                    {
                        "type": "error",
                        "message": "Invalid message format. Expected JSON with lat, lng, timestamp",
                    },
                )
            except (ValueError, ValidationError) as e:
                logger.error(f"Validation error from {authenticated_user.user_id}: {str(e)}")
                await connection_manager.send_personal_message(
                    authenticated_user.user_id,
                    {"type": "error", "message": f"Validation error: {str(e)}"},
                )

    except WebSocketDisconnect:
        if authenticated_user:
            await connection_manager.disconnect(authenticated_user.user_id)
            logger.info(f"User {authenticated_user.user_id} disconnected")

    except Exception as e:
        logger.error(f"WebSocket error for {user_id}: {str(e)}")
        await connection_manager.disconnect(user_id)


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/v1/health",
            "users": "/api/v1/users",
            "rooms": "/api/v1/rooms",
            "checkin": "POST /api/v1/checkin",
            "checkout": "POST /api/v1/checkout",
            "websocket": "WS /ws/{user_id}",
        },
    }


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,
    )
