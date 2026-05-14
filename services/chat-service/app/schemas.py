from datetime import datetime

from pydantic import BaseModel, Field

from app.models import MessageStatus, MessageType


class HealthResponse(BaseModel):
    service: str
    status: str


class ConversationCreate(BaseModel):
    participant_id: str = Field(min_length=1, max_length=128)
    match_id: str | None = Field(default=None, max_length=128)


class ConversationResponse(BaseModel):
    id: str
    participant_ids: list[str]
    match_id: str | None = None
    last_message: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    unread_count: int = 0


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    message_type: MessageType = MessageType.TEXT


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    receiver_id: str
    content: str
    message_type: MessageType = MessageType.TEXT
    status: MessageStatus = MessageStatus.SENT
    created_at: datetime
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    deleted_at: datetime | None = None


class ReadMessagesResponse(BaseModel):
    message: str
    updated_count: int


class PresenceResponse(BaseModel):
    user_id: str
    is_online: bool


class ErrorResponse(BaseModel):
    detail: str
