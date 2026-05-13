from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: str
    status: str


class TokenPayload(BaseModel):
    sub: str
    email: str | None = None
    exp: int | None = None
