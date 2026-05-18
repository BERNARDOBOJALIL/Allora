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

    user_id: str | None = None
    room_id: str


class CheckoutRequest(BaseModel):
    """Check-out request."""

    user_id: str | None = None
    room_id: str


class SpaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=800)
    photo_base64: str = Field(min_length=1)
    lat: float
    lng: float
    radius_km: float = Field(default=1.0, gt=0.0, le=20.0)
    user_id: str | None = None


class SpaceJoinRequest(BaseModel):
    user_id: str | None = None
    lat: float | None = None
    lng: float | None = None


class SpaceResponse(BaseModel):
    space_id: str
    name: str
    description: str
    photo_base64: str
    owner_user_id: str
    lat: float
    lng: float
    radius_km: float
    members: list[str]
    chat_conversation_id: str | None = None
    created_at: str
    expires_at: str | None = None


class SpacesResponse(BaseModel):
    count: int
    spaces: list[SpaceResponse]
