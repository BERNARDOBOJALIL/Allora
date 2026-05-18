import logging
from contextlib import asynccontextmanager
from typing import Annotated

from bson import ObjectId
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from redis.asyncio import Redis

from app.cache import (
    close_redis_connection,
    connect_to_redis,
    conversation_cache_key,
    get_redis,
    presence_key,
    unread_key,
)
from app.database import close_mongo_connection, connect_to_mongo, get_database
from app.events import close_rabbitmq_connection, connect_to_rabbitmq, publish_event
from app.models import MessageStatus, serialize_conversation, serialize_message, utc_now
from app.schemas import (
    ConversationCreate,
    ConversationResponse,
    GroupConversationCreate,
    HealthResponse,
    MessageCreate,
    MessageResponse,
    PresenceResponse,
    ReadMessagesResponse,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("chat-service")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_to_mongo()
    await connect_to_redis()
    await connect_to_rabbitmq()
    logger.info("chat-service dependencies ready")
    yield
    await close_rabbitmq_connection()
    await close_redis_connection()
    await close_mongo_connection()


app = FastAPI(title="ALLORA Chat Service", version="0.1.0", lifespan=lifespan)
UserIdHeader = Annotated[str, Header(alias="X-User-Id", min_length=1)]


def participant_key(user_a: str, user_b: str) -> str:
    return ":".join(sorted([user_a, user_b]))


def require_object_id(value: str, name: str = "id") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name} invalido")
    return ObjectId(value)


async def get_conversation_for_user(
    db: AsyncIOMotorDatabase,
    conversation_id: str,
    user_id: str,
) -> dict:
    conversation = await db.conversations.find_one(
        {
            "_id": require_object_id(conversation_id, "conversation_id"),
            "participant_ids": user_id,
        }
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversacion no encontrada",
        )
    return conversation


def get_receiver_id(conversation: dict, sender_id: str) -> str:
    participants = conversation.get("participant_ids", [])
    for participant_id in participants:
        if participant_id != sender_id:
            return participant_id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="La conversacion no tiene receptor valido",
    )


def is_group_conversation(conversation: dict) -> bool:
    return conversation.get("conversation_type") == "GROUP"


async def get_group_conversation_for_user(
    db: AsyncIOMotorDatabase,
    conversation_id: str,
    user_id: str,
) -> dict:
    conversation = await db.conversations.find_one(
        {
            "_id": require_object_id(conversation_id, "conversation_id"),
            "conversation_type": "GROUP",
            "participant_ids": user_id,
        }
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversacion de grupo no encontrada",
        )
    return conversation


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(service="chat-service", status="ok")


@app.post(
    "/conversations",
    response_model=ConversationResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    user_id: UserIdHeader,
    db: AsyncIOMotorDatabase = Depends(get_database),
    redis: Redis = Depends(get_redis),
) -> ConversationResponse:
    if payload.participant_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes crear una conversacion contigo mismo",
        )

    key = participant_key(user_id, payload.participant_id)
    existing = await db.conversations.find_one({"participant_key": key})
    if existing:
        unread_count = int(await redis.get(unread_key(user_id, str(existing["_id"]))) or 0)
        return ConversationResponse(**serialize_conversation(existing, unread_count))

    now = utc_now()
    conversation_doc = {
        "participant_ids": sorted([user_id, payload.participant_id]),
        "participant_key": key,
        "match_id": payload.match_id,
        "last_message": None,
        "last_message_at": None,
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = await db.conversations.insert_one(conversation_doc)
    except DuplicateKeyError:
        existing = await db.conversations.find_one({"participant_key": key})
        unread_count = int(await redis.get(unread_key(user_id, str(existing["_id"]))) or 0)
        return ConversationResponse(**serialize_conversation(existing, unread_count))

    conversation_doc["_id"] = result.inserted_id
    conversation_id = str(result.inserted_id)
    await redis.hset(
        conversation_cache_key(conversation_id),
        mapping={
            "participant_key": key,
            "updated_at": now.isoformat(),
        },
    )
    await publish_event(
        "conversation.created",
        serialize_conversation(conversation_doc),
    )
    return ConversationResponse(**serialize_conversation(conversation_doc))


@app.post(
    "/group-conversations",
    response_model=ConversationResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_group_conversation(
    payload: GroupConversationCreate,
    user_id: UserIdHeader,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ConversationResponse:
    participant_key = f"group:{payload.group_id}"
    existing = await db.conversations.find_one({"participant_key": participant_key})
    if existing:
        return ConversationResponse(**serialize_conversation(existing))

    now = utc_now()
    conversation_doc = {
        "participant_ids": [user_id],
        "participant_key": participant_key,
        "conversation_type": "GROUP",
        "group_id": payload.group_id,
        "group_name": payload.name,
        "group_description": payload.description,
        "group_photo_base64": payload.photo_base64,
        "match_id": None,
        "last_message": None,
        "last_message_at": None,
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = await db.conversations.insert_one(conversation_doc)
    except DuplicateKeyError:
        existing = await db.conversations.find_one({"participant_key": participant_key})
        return ConversationResponse(**serialize_conversation(existing))

    conversation_doc["_id"] = result.inserted_id
    await publish_event(
        "group.conversation.created",
        serialize_conversation(conversation_doc),
    )
    return ConversationResponse(**serialize_conversation(conversation_doc))


@app.post(
    "/group-conversations/{conversation_id}/join",
    response_model=ConversationResponse,
    response_model_exclude_none=True,
)
async def join_group_conversation(
    conversation_id: str,
    user_id: UserIdHeader,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ConversationResponse:
    conversation = await db.conversations.find_one(
        {
            "_id": require_object_id(conversation_id, "conversation_id"),
            "conversation_type": "GROUP",
        }
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo no encontrado")

    await db.conversations.update_one(
        {"_id": conversation["_id"]},
        {
            "$addToSet": {"participant_ids": user_id},
            "$set": {"updated_at": utc_now()},
        },
    )
    updated = await db.conversations.find_one({"_id": conversation["_id"]})
    return ConversationResponse(**serialize_conversation(updated))


@app.get("/group-conversations", response_model=list[ConversationResponse])
async def list_group_conversations(
    user_id: UserIdHeader,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[ConversationResponse]:
    cursor = db.conversations.find(
        {
            "conversation_type": "GROUP",
            "participant_ids": user_id,
        }
    ).sort("updated_at", -1)
    return [ConversationResponse(**serialize_conversation(c)) async for c in cursor]


@app.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    user_id: UserIdHeader,
    db: AsyncIOMotorDatabase = Depends(get_database),
    redis: Redis = Depends(get_redis),
) -> list[ConversationResponse]:
    cursor = db.conversations.find({"participant_ids": user_id}).sort("updated_at", -1)
    conversations = []
    async for conversation in cursor:
        conversation_id = str(conversation["_id"])
        unread_count = int(await redis.get(unread_key(user_id, conversation_id)) or 0)
        conversations.append(ConversationResponse(**serialize_conversation(conversation, unread_count)))
    return conversations


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: str,
    user_id: UserIdHeader,
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[MessageResponse]:
    await get_conversation_for_user(db, conversation_id, user_id)
    cursor = (
        db.messages.find({"conversation_id": conversation_id, "deleted_at": None})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    messages = [MessageResponse(**serialize_message(message)) async for message in cursor]
    return list(reversed(messages))


@app.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: str,
    payload: MessageCreate,
    user_id: UserIdHeader,
    db: AsyncIOMotorDatabase = Depends(get_database),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    conversation = await get_conversation_for_user(db, conversation_id, user_id)
    receiver_id = get_receiver_id(conversation, user_id)
    now = utc_now()
    content = payload.content.strip()

    message_doc = {
        "conversation_id": conversation_id,
        "sender_id": user_id,
        "receiver_id": receiver_id,
        "content": content,
        "message_type": payload.message_type.value,
        "status": MessageStatus.SENT.value,
        "created_at": now,
        "delivered_at": None,
        "read_at": None,
        "deleted_at": None,
    }
    result = await db.messages.insert_one(message_doc)
    message_doc["_id"] = result.inserted_id

    await db.conversations.update_one(
        {"_id": conversation["_id"]},
        {
            "$set": {
                "last_message": content,
                "last_message_at": now,
                "updated_at": now,
            }
        },
    )
    await redis.incr(unread_key(receiver_id, conversation_id))
    await redis.hset(
        conversation_cache_key(conversation_id),
        mapping={
            "last_message": content,
            "last_message_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
    )

    serialized = serialize_message(message_doc)
    await publish_event("message.sent", serialized)
    return MessageResponse(**serialized)


@app.get("/group-conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_group_messages(
    conversation_id: str,
    user_id: UserIdHeader,
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[MessageResponse]:
    await get_group_conversation_for_user(db, conversation_id, user_id)
    cursor = (
        db.messages.find({"conversation_id": conversation_id, "deleted_at": None})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    messages = [MessageResponse(**serialize_message(message)) async for message in cursor]
    return list(reversed(messages))


@app.post(
    "/group-conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_group_message(
    conversation_id: str,
    payload: MessageCreate,
    user_id: UserIdHeader,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    conversation = await get_group_conversation_for_user(db, conversation_id, user_id)
    now = utc_now()
    content = payload.content.strip()

    message_doc = {
        "conversation_id": conversation_id,
        "sender_id": user_id,
        "receiver_id": None,
        "content": content,
        "message_type": payload.message_type.value,
        "status": MessageStatus.SENT.value,
        "created_at": now,
        "delivered_at": None,
        "read_at": None,
        "deleted_at": None,
    }
    result = await db.messages.insert_one(message_doc)
    message_doc["_id"] = result.inserted_id

    await db.conversations.update_one(
        {"_id": conversation["_id"]},
        {
            "$set": {
                "last_message": content,
                "last_message_at": now,
                "updated_at": now,
            }
        },
    )

    serialized = serialize_message(message_doc)
    serialized["group_id"] = conversation.get("group_id")
    await publish_event("message.sent", serialized)
    return MessageResponse(**serialize_message(message_doc))


@app.post(
    "/conversations/{conversation_id}/read",
    response_model=ReadMessagesResponse,
)
async def mark_conversation_as_read(
    conversation_id: str,
    user_id: UserIdHeader,
    db: AsyncIOMotorDatabase = Depends(get_database),
    redis: Redis = Depends(get_redis),
) -> ReadMessagesResponse:
    await get_conversation_for_user(db, conversation_id, user_id)
    now = utc_now()
    result = await db.messages.update_many(
        {
            "conversation_id": conversation_id,
            "receiver_id": user_id,
            "read_at": None,
            "deleted_at": None,
        },
        {
            "$set": {
                "status": MessageStatus.READ.value,
                "read_at": now,
            }
        },
    )
    await redis.delete(unread_key(user_id, conversation_id))
    await publish_event(
        "messages.read",
        {
            "conversation_id": conversation_id,
            "reader_id": user_id,
            "updated_count": result.modified_count,
            "read_at": now,
        },
    )
    return ReadMessagesResponse(
        message="Mensajes marcados como leidos",
        updated_count=result.modified_count,
    )


@app.post("/presence/online", response_model=PresenceResponse)
async def mark_online(
    user_id: UserIdHeader,
    redis: Redis = Depends(get_redis),
) -> PresenceResponse:
    await redis.set(presence_key(user_id), "online", ex=90)
    await publish_event("user.online", {"user_id": user_id, "at": utc_now()})
    return PresenceResponse(user_id=user_id, is_online=True)


@app.post("/presence/offline", response_model=PresenceResponse)
async def mark_offline(
    user_id: UserIdHeader,
    redis: Redis = Depends(get_redis),
) -> PresenceResponse:
    await redis.delete(presence_key(user_id))
    await publish_event("user.offline", {"user_id": user_id, "at": utc_now()})
    return PresenceResponse(user_id=user_id, is_online=False)


@app.get("/presence/{target_user_id}", response_model=PresenceResponse)
async def get_presence(
    target_user_id: str,
    _: UserIdHeader,
    redis: Redis = Depends(get_redis),
) -> PresenceResponse:
    return PresenceResponse(
        user_id=target_user_id,
        is_online=await redis.exists(presence_key(target_user_id)) > 0,
    )
