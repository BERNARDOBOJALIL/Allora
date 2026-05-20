from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import MatchStatus


class UserPreferencesSchema(BaseModel):
    """User preferences for matching"""
    edad_minima: int = Field(ge=18, le=100, default=18)
    edad_maxima: int = Field(ge=18, le=100, default=65)
    distancia_maxima_km: float = Field(ge=1, le=500, default=50)
    genero_preferido: Optional[str] = None
    intereses_comunes: list[str] = Field(default_factory=list)


class UserProfileSchema(BaseModel):
    """User profile for matching"""
    id: str
    nombre: str
    edad: int
    genero: str
    ubicacion: dict[str, Any]  # {lat, lng, ciudad}
    intereses: list[str] = Field(default_factory=list)
    bio: Optional[str] = None
    fotos: list[str] = Field(default_factory=list)
    preferencias: UserPreferencesSchema


class MatchCreateRequest(BaseModel):
    """Request to create a match"""
    user_a_id: str
    user_b_id: str


class MatchResponse(BaseModel):
    """Match response"""
    id: str
    user_a_id: str
    user_b_id: str
    status: MatchStatus = MatchStatus.PENDING
    compatibility_score: float
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class MatchListResponse(BaseModel):
    """List of matches"""
    total: int
    matches: list[MatchResponse]


class PotentialMatchResponse(BaseModel):
    """Potential match candidate returned by the matching engine"""
    user_id: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class PotentialMatchListResponse(BaseModel):
    """List of potential match candidates"""
    total: int
    matches: list[PotentialMatchResponse]


class MatchUpdateRequest(BaseModel):
    """Update match status"""
    status: MatchStatus


class MatchCompatibilityRequest(BaseModel):
    """Request to calculate compatibility"""
    user_a_id: str
    user_b_id: str


class MatchCompatibilityResponse(BaseModel):
    """Compatibility calculation result"""
    user_a_id: str
    user_b_id: str
    score: float
    reasons: list[str]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    service: str = "match-service"
