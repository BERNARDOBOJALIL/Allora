from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.config import settings


client: AsyncIOMotorClient | None = None
database: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> None:
    global client, database
    client = AsyncIOMotorClient(settings.mongo_uri, tz_aware=True)
    database = client[settings.chat_mongo_db_name]
    await create_indexes(database)


async def close_mongo_connection() -> None:
    if client:
        client.close()


def get_database() -> AsyncIOMotorDatabase:
    if database is None:
        raise RuntimeError("MongoDB connection has not been initialized")
    return database


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.conversations.create_index([("participant_key", ASCENDING)], unique=True)
    await db.conversations.create_index([("participant_ids", ASCENDING)])
    await db.conversations.create_index([("match_id", ASCENDING)])
    await db.conversations.create_index([("updated_at", DESCENDING)])

    await db.messages.create_index([("conversation_id", ASCENDING), ("created_at", DESCENDING)])
    await db.messages.create_index([("receiver_id", ASCENDING), ("status", ASCENDING)])
    await db.messages.create_index([("sender_id", ASCENDING), ("created_at", DESCENDING)])
