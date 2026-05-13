from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LocationUpdate(BaseModel):
    """Location update received from WebSocket client."""

    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")
    timestamp: str = Field(..., description="ISO format timestamp")


class UserLocation(BaseModel):
    """User location data."""

    user_id: str
    lat: float
    lng: float
    timestamp: str
    room_id: Optional[str] = None


class Room(BaseModel):
    """Virtual room for grouping users."""

    room_id: str
    user_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    timestamp: str


class UsersResponse(BaseModel):
    """Connected users response."""

    connected_users: int
    users: list[str]


class RoomsResponse(BaseModel):
    """Active rooms response."""

    active_rooms: int
    rooms: dict[str, list[str]]


class CheckinRequest(BaseModel):
    """Check-in request."""

    user_id: str
    room_id: str


class CheckoutRequest(BaseModel):
    """Check-out request."""

    user_id: str
    room_id: str
