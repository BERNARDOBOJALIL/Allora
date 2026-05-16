from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING
import asyncio
import time

from app.config import settings


client: AsyncIOMotorClient | None = None
database: AsyncIOMotorDatabase | None = None


async def connect_to_mongo(retry_seconds: int = 30) -> None:
    global client, database
    deadline = time.time() + retry_seconds
    last_exc: Exception | None = None
    while True:
        try:
            client = AsyncIOMotorClient(settings.mongo_uri, tz_aware=True, serverSelectionTimeoutMS=2000)
            database = client[settings.mongo_db_name]
            await create_indexes(database)
            return
        except Exception as exc:
            last_exc = exc
            if time.time() > deadline:
                # raise the last exception so startup fails visibly after retries
                raise
            await asyncio.sleep(1)


async def close_mongo_connection() -> None:
    if client:
        client.close()


def get_database() -> AsyncIOMotorDatabase:
    if database is None:
        raise RuntimeError("MongoDB connection has not been initialized")
    return database


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.users.create_index(
        [("email", ASCENDING)],
        unique=True,
        partialFilterExpression={"email": {"$type": "string"}},
    )
    await db.users.create_index(
        [("telefono", ASCENDING)],
        unique=True,
        partialFilterExpression={"telefono": {"$type": "string"}},
    )
    await db.users.create_index(
        [("oauth_provider", ASCENDING), ("oauth_provider_id", ASCENDING)],
        unique=True,
        partialFilterExpression={
            "oauth_provider": {"$type": "string"},
            "oauth_provider_id": {"$type": "string"},
        },
    )
    await db.refresh_tokens.create_index([("token_hash", ASCENDING)], unique=True)
    await db.refresh_tokens.create_index([("user_id", ASCENDING)])
    await db.refresh_tokens.create_index([("expires_at", ASCENDING)])
    await db.verification_codes.create_index([("code_hash", ASCENDING)])
    await db.verification_codes.create_index(
        [("purpose", ASCENDING), ("email", ASCENDING), ("telefono", ASCENDING)]
    )
    await db.verification_codes.create_index([("expires_at", ASCENDING)])
