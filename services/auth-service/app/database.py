from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING

from app.config import settings


client: AsyncIOMotorClient | None = None
database: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> None:
    global client, database
    client = AsyncIOMotorClient(settings.mongo_uri, tz_aware=True)
    database = client[settings.mongo_db_name]
    await create_indexes(database)


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
