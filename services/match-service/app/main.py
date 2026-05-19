import logging
from contextlib import asynccontextmanager

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.database import close_mongo_connection, connect_to_mongo, get_database
from app.matching_engine import MatchingEngine
from app.models import MatchStatus, serialize_match, utc_now
from app.schemas import (
    HealthResponse,
    MatchCompatibilityRequest,
    MatchCompatibilityResponse,
    MatchCreateRequest,
    MatchListResponse,
    MatchResponse,
    MatchUpdateRequest,
)

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("match-service")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_to_mongo()
    logger.info("match-service dependencies ready")
    yield
    await close_mongo_connection()


app = FastAPI(
    title="Match Service",
    description="Service for user matching and compatibility calculations",
    version="1.0.0",
    lifespan=lifespan,
)


# Dependency to get matching engine
async def get_matching_engine(db: AsyncIOMotorDatabase = Depends(get_database)):
    return MatchingEngine(db)


# Health check
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", service="match-service")


# Get potential matches for a user
@app.get("/users/{user_id}/matches", response_model=MatchListResponse)
async def get_potential_matches(
    user_id: str,
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    engine: MatchingEngine = Depends(get_matching_engine),
):
    """
    Get potential matches for a user based on compatibility
    """
    try:
        matches = await engine.find_matches(user_id, limit=limit, skip=skip)
        return MatchListResponse(total=len(matches), matches=matches)
    except Exception as e:
        logger.error(f"Error finding matches for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error finding matches",
        )


# Calculate compatibility between two users
@app.post("/compatibility")
async def calculate_compatibility(
    request: MatchCompatibilityRequest,
    engine: MatchingEngine = Depends(get_matching_engine),
):
    """
    Calculate compatibility score between two users
    """
    try:
        user_a = await engine.get_user_profile(request.user_a_id)
        user_b = await engine.get_user_profile(request.user_b_id)
        
        if not user_a or not user_b:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both users not found",
            )
        
        loc_a = await engine.get_user_location(request.user_a_id)
        loc_b = await engine.get_user_location(request.user_b_id)
        
        score, reasons = await engine.calculate_compatibility(user_a, user_b, loc_a, loc_b)
        
        return MatchCompatibilityResponse(
            user_a_id=request.user_a_id,
            user_b_id_id=request.user_b_id,
            score=score,
            reasons=reasons,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating compatibility: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error calculating compatibility",
        )


# Create a match
@app.post("/matches", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
async def create_match(
    request: MatchCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    engine: MatchingEngine = Depends(get_matching_engine),
):
    """
    Create a match between two users
    """
    try:
        # Check if users exist
        user_a = await engine.get_user_profile(request.user_a_id)
        user_b = await engine.get_user_profile(request.user_b_id)
        
        if not user_a or not user_b:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both users not found",
            )
        
        # Check if match already exists
        existing = await db["matches"].find_one({
            "$or": [
                {"user_a_id": request.user_a_id, "user_b_id": request.user_b_id},
                {"user_a_id": request.user_b_id, "user_b_id": request.user_a_id},
            ]
        })
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Match already exists between these users",
            )
        
        # Create match
        match = await engine.create_match(request.user_a_id, request.user_b_id)
        
        if not match:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not create match - compatibility score too low",
            )
        
        return MatchResponse(**serialize_match(match))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating match: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating match",
        )


# Get match by ID
@app.get("/matches/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Get a match by ID
    """
    try:
        match = await db["matches"].find_one({"_id": ObjectId(match_id)})
        
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Match not found",
            )
        
        return MatchResponse(**serialize_match(match))
    except Exception as e:
        logger.error(f"Error getting match {match_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error getting match",
        )


# Get all matches for a user
@app.get("/users/{user_id}/all-matches", response_model=MatchListResponse)
async def get_user_matches(
    user_id: str,
    status: str = Query(None, description="Filter by match status"),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Get all matches for a user (both initiated and received)
    """
    try:
        query = {
            "$or": [
                {"user_a_id": user_id},
                {"user_b_id": user_id},
            ]
        }
        
        if status:
            query["status"] = status
        
        total = await db["matches"].count_documents(query)
        matches = await db["matches"].find(query).skip(skip).limit(limit).to_list(limit)
        
        return MatchListResponse(
            total=total,
            matches=[MatchResponse(**serialize_match(m)) for m in matches],
        )
    except Exception as e:
        logger.error(f"Error getting matches for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error getting matches",
        )


# Update match status
@app.put("/matches/{match_id}", response_model=MatchResponse)
async def update_match_status(
    match_id: str,
    request: MatchUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Update match status (accept/reject)
    """
    try:
        match = await db["matches"].find_one({"_id": ObjectId(match_id)})
        
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Match not found",
            )
        
        # Update status
        update_result = await db["matches"].update_one(
            {"_id": ObjectId(match_id)},
            {
                "$set": {
                    "status": request.status,
                    "updated_at": utc_now(),
                }
            },
        )
        
        if update_result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not update match",
            )
        
        updated_match = await db["matches"].find_one({"_id": ObjectId(match_id)})
        return MatchResponse(**serialize_match(updated_match))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating match {match_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating match",
        )


# Delete match
@app.delete("/matches/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_match(
    match_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Delete a match
    """
    try:
        result = await db["matches"].delete_one({"_id": ObjectId(match_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Match not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting match {match_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting match",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
