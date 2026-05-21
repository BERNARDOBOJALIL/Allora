from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class Plan(StrEnum):
    FREE = "FREE"
    PREMIUM = "PREMIUM"


class VerificationPurpose(StrEnum):
    EMAIL_VERIFY = "EMAIL_VERIFY"
    PHONE_VERIFY = "PHONE_VERIFY"
    PASSWORD_RESET = "PASSWORD_RESET"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(user["_id"]),
        "nombre": user.get("nombre"),
        "email": user.get("email"),
        "telefono": user.get("telefono"),
        "oauth_provider": user.get("oauth_provider"),
        "role": user.get("role", Role.USER.value),
        "plan": user.get("plan", Plan.FREE.value),
        "is_active": user.get("is_active", True),
        "is_email_verified": user.get("is_email_verified", False),
        "is_phone_verified": user.get("is_phone_verified", False),
        "is_blocked": user.get("is_blocked", False),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
        "last_login": user.get("last_login"),
        "password_changed_at": user.get("password_changed_at"),
    }
