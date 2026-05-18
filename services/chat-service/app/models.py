from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class MessageType(StrEnum):
    TEXT = "TEXT"


class MessageStatus(StrEnum):
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_conversation(
    conversation: dict[str, Any],
    unread_count: int = 0,
) -> dict[str, Any]:
    return {
        "id": str(conversation["_id"]),
        "participant_ids": conversation.get("participant_ids", []),
        "conversation_type": conversation.get("conversation_type", "DIRECT"),
        "group_id": conversation.get("group_id"),
        "match_id": conversation.get("match_id"),
        "last_message": conversation.get("last_message"),
        "last_message_at": conversation.get("last_message_at"),
        "created_at": conversation.get("created_at"),
        "updated_at": conversation.get("updated_at"),
        "unread_count": unread_count,
    }


def serialize_message(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(message["_id"]),
        "conversation_id": message.get("conversation_id"),
        "sender_id": message.get("sender_id"),
        "receiver_id": message.get("receiver_id"),
        "content": message.get("content"),
        "message_type": message.get("message_type", MessageType.TEXT.value),
        "status": message.get("status", MessageStatus.SENT.value),
        "created_at": message.get("created_at"),
        "delivered_at": message.get("delivered_at"),
        "read_at": message.get("read_at"),
        "deleted_at": message.get("deleted_at"),
    }
