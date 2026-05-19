from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional


class MatchStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_match(match: dict[str, Any]) -> dict[str, Any]:
    """Serialize a match document from MongoDB"""
    return {
        "id": str(match["_id"]),
        "user_a_id": str(match["user_a_id"]),
        "user_b_id": str(match["user_b_id"]),
        "status": match.get("status", MatchStatus.PENDING.value),
        "compatibility_score": match.get("compatibility_score", 0.0),
        "reasons": match.get("reasons", []),
        "unlock_level": match.get("unlock_level", 0), 
        "created_at": match.get("created_at"),
        "updated_at": match.get("updated_at"),
        "expires_at": match.get("expires_at"),
        "metadata": match.get("metadata", {}),
    }


def serialize_user_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Serialize a user profile for matching"""
    return {
        "id": str(profile["_id"]),
        "nombre": profile.get("nombre"),
        "edad": profile.get("edad"),
        "genero": profile.get("genero"),
        "ubicacion": profile.get("ubicacion"),
        "intereses": profile.get("intereses", []),
        "bio": profile.get("bio"),
        "fotos": profile.get("fotos", []),
        "preferencias": profile.get("preferencias", {}),
    }
