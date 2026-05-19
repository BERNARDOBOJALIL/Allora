import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

logger = logging.getLogger("match-service")

_db_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo():
    """Connect to MongoDB"""
    global _db_client, _db
    _db_client = AsyncIOMotorClient(settings.mongodb_url)
    _db = _db_client[settings.mongodb_db]
    
    # Create indexes
    await _db["matches"].create_index("user_a_id")
    await _db["matches"].create_index("user_b_id")
    await _db["matches"].create_index([("user_a_id", 1), ("user_b_id", 1)], unique=True)
    await _db["matches"].create_index("status")
    await _db["matches"].create_index("created_at")
    await _db["matches"].create_index("expires_at")
    
    await _db["user_profiles"].create_index("user_id", unique=True)
    await _db["user_profiles"].create_index("genero")
    await _db["user_profiles"].create_index("intereses")
    
    logger.info("Connected to MongoDB")


async def close_mongo_connection():
    """Close MongoDB connection"""
    global _db_client
    if _db_client:
        _db_client.close()
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """Get database instance"""
    if _db is None:
        raise RuntimeError("Database not connected")
    return _db
