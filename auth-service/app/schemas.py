from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import Plan, Role
from app.security import normalize_email, normalize_phone


class UserResponse(BaseModel):
    id: str
    nombre: str
    email: str | None = None
    telefono: str | None = None
    oauth_provider: str | None = None
    role: Role = Role.USER
    plan: Plan = Plan.FREE
    is_active: bool = True
    is_email_verified: bool = False
    is_phone_verified: bool = False
    is_blocked: bool = False
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None
    password_changed_at: datetime | None = None
    dev_codes: dict[str, str] | None = None

    model_config = ConfigDict(use_enum_values=True)


class RegisterRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    email: EmailStr | None = None
    telefono: str | None = Field(default=None, min_length=5, max_length=30)
    role: Role = Role.USER
    plan: Plan = Plan.FREE

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: Any) -> Any:
        return normalize_email(value)

    @field_validator("telefono", mode="before")
    @classmethod
    def clean_phone(cls, value: Any) -> Any:
        return normalize_phone(value)

    @model_validator(mode="after")
    def validate_identifier(self) -> "RegisterRequest":
        if not self.email and not self.telefono:
            raise ValueError("Debe existir al menos email o telefono")
        return self


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier", mode="before")
    @classmethod
    def clean_identifier(cls, value: Any) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("Identifier requerido")
        return cleaned


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class MessageResponse(BaseModel):
    message: str
    dev_code: str | None = None


class MeUpdateRequest(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    telefono: str | None = Field(default=None, min_length=5, max_length=30)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: Any) -> Any:
        return normalize_email(value)

    @field_validator("telefono", mode="before")
    @classmethod
    def clean_phone(cls, value: Any) -> Any:
        return normalize_phone(value)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr | None = None
    telefono: str | None = Field(default=None, min_length=5, max_length=30)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: Any) -> Any:
        return normalize_email(value)

    @field_validator("telefono", mode="before")
    @classmethod
    def clean_phone(cls, value: Any) -> Any:
        return normalize_phone(value)

    @model_validator(mode="after")
    def validate_identifier(self) -> "ForgotPasswordRequest":
        if not self.email and not self.telefono:
            raise ValueError("Debe existir email o telefono")
        return self


class ResetPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("identifier", mode="before")
    @classmethod
    def clean_identifier(cls, value: Any) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("Identifier requerido")
        return cleaned


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: Any) -> Any:
        return normalize_email(value)


class VerifyPhoneRequest(BaseModel):
    telefono: str = Field(min_length=5, max_length=30)
    code: str = Field(min_length=4, max_length=12)

    @field_validator("telefono", mode="before")
    @classmethod
    def clean_phone(cls, value: Any) -> Any:
        return normalize_phone(value)


class OAuthLoginRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=60)
    provider_user_id: str = Field(min_length=1, max_length=160)
    email: EmailStr | None = None
    nombre: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("provider", mode="before")
    @classmethod
    def clean_provider(cls, value: Any) -> str:
        return str(value).strip().lower()

    @field_validator("provider_user_id", mode="before")
    @classmethod
    def clean_provider_user_id(cls, value: Any) -> str:
        return str(value).strip()

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: Any) -> Any:
        return normalize_email(value)
