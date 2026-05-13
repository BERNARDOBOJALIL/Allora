import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.logger import setup_logger
from app.websocket_manager import ConnectionManager
from app.room_manager import RoomManager
from app.models import LocationUpdate
from app.api.routes import init_routes, router

logger = setup_logger(__name__, settings.log_level)

# Global managers
connection_manager = ConnectionManager()
room_manager = RoomManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info(f"Starting {settings.service_name}")
    yield
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
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time location updates."""
    try:
        await connection_manager.connect(user_id, websocket)
        logger.info(f"WebSocket connection established for user {user_id}")

        while True:
            try:
                # Receive JSON message from client
                data = await websocket.receive_text()
                message = json.loads(data)

                # Validate location update
                location_update = LocationUpdate(**message)

                # Store location
                connection_manager.store_location(
                    user_id,
                    {
                        "lat": location_update.lat,
                        "lng": location_update.lng,
                        "timestamp": location_update.timestamp,
                    },
                )

                # Broadcast to users in same room
                await connection_manager.broadcast_location(
                    user_id,
                    {
                        "lat": location_update.lat,
                        "lng": location_update.lng,
                        "timestamp": location_update.timestamp,
                    },
                )

                logger.info(
                    f"Location update from {user_id}: lat={location_update.lat}, lng={location_update.lng}"
                )

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from {user_id}: {str(e)}")
                await connection_manager.send_personal_message(
                    user_id,
                    {
                        "type": "error",
                        "message": "Invalid message format. Expected JSON with lat, lng, timestamp",
                    },
                )
            except ValueError as e:
                logger.error(f"Validation error from {user_id}: {str(e)}")
                await connection_manager.send_personal_message(
                    user_id,
                    {"type": "error", "message": f"Validation error: {str(e)}"},
                )

    except WebSocketDisconnect:
        await connection_manager.disconnect(user_id)
        logger.info(f"User {user_id} disconnected")

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
