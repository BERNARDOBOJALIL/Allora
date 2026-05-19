import logging
from datetime import datetime, timedelta, timezone
from math import radians, cos, sin, asin, sqrt
from typing import Optional

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.models import MatchStatus, utc_now

logger = logging.getLogger("match-service")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points on Earth in kilometers
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r


class MatchingEngine:
    """Core matching algorithm"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.auth_service_url = settings.auth_service_url
        self.location_service_url = settings.location_service_url
        self.max_distance = settings.max_distance_km
        self.min_score = settings.min_compatibility_score
    
    async def get_user_profile(self, user_id: str) -> Optional[dict]:
        """Get user profile from auth service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.auth_service_url}/users/{user_id}",
                    timeout=5.0
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.error(f"Error fetching user profile {user_id}: {e}")
        return None
    
    async def get_user_location(self, user_id: str) -> Optional[dict]:
        """Get user location from location service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.location_service_url}/api/v1/locations/{user_id}",
                    timeout=5.0
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.error(f"Error fetching user location {user_id}: {e}")
        return None
    
    async def calculate_compatibility(
        self,
        user_a: dict,
        user_b: dict,
        location_a: Optional[dict] = None,
        location_b: Optional[dict] = None,
    ) -> tuple[float, list[str]]:
        """
        Calculate compatibility score between two users
        Returns: (score, reasons)
        """
        score = 0.0
        reasons = []
        
        # Age compatibility (max 25 points)
        age_a = user_a.get("edad", 0)
        age_b = user_b.get("edad", 0)
        prefs_a = user_a.get("preferencias", {})
        prefs_b = user_b.get("preferencias", {})
        
        age_min_a = prefs_a.get("edad_minima", 18)
        age_max_a = prefs_a.get("edad_maxima", 65)
        age_min_b = prefs_b.get("edad_minima", 18)
        age_max_b = prefs_b.get("edad_maxima", 65)
        
        if age_min_a <= age_b <= age_max_a and age_min_b <= age_a <= age_max_b:
            score += 25
            reasons.append("Age preferences match")
        else:
            return 0.0, ["Age preferences don't match"]
        
        # Gender preference compatibility (max 20 points)
        gender_a = user_a.get("genero", "").lower()
        gender_b = user_b.get("genero", "").lower()
        pref_gender_a = prefs_a.get("genero_preferido", "").lower() if prefs_a.get("genero_preferido") else None
        pref_gender_b = prefs_b.get("genero_preferido", "").lower() if prefs_b.get("genero_preferido") else None
        
        gender_match = True
        if pref_gender_a and gender_b != pref_gender_a:
            gender_match = False
        if pref_gender_b and gender_a != pref_gender_b:
            gender_match = False
        
        if gender_match:
            score += 20
            reasons.append("Gender preferences compatible")
        else:
            return 0.0, ["Gender preferences don't match"]
        
        # Distance compatibility (max 25 points)
        if location_a and location_b:
            try:
                distance = haversine_distance(
                    location_a.get("lat", 0),
                    location_a.get("lng", 0),
                    location_b.get("lat", 0),
                    location_b.get("lng", 0),
                )
                
                max_dist_a = prefs_a.get("distancia_maxima_km", settings.max_distance_km)
                max_dist_b = prefs_b.get("distancia_maxima_km", settings.max_distance_km)
                
                if distance <= max_dist_a and distance <= max_dist_b:
                    # More points for closer users
                    distance_score = max(0, 25 * (1 - distance / max(max_dist_a, max_dist_b)))
                    score += distance_score
                    reasons.append(f"Close proximity ({distance:.1f} km)")
                else:
                    return 0.0, [f"Distance too far ({distance:.1f} km)"]
            except Exception as e:
                logger.warning(f"Error calculating distance: {e}")
        
        # Common interests (max 30 points)
        interests_a = set(user_a.get("intereses", []))
        interests_b = set(user_b.get("intereses", []))
        
        if interests_a and interests_b:
            common_interests = interests_a & interests_b
            if common_interests:
                interest_score = min(30, len(common_interests) * 5)
                score += interest_score
                reasons.append(f"Shared interests: {', '.join(list(common_interests)[:3])}")
        
        return min(100.0, score), reasons
    
    async def find_matches(
        self,
        user_id: str,
        limit: int = 10,
        skip: int = 0,
    ) -> list[dict]:
        """
        Find potential matches for a user
        """
        # Get user profile
        user = await self.get_user_profile(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            return []
        
        # Get user location
        location = await self.get_user_location(user_id)
        
        # Get preferences
        prefs = user.get("preferencias", {})
        
        # Build query to find candidates
        gender_filter = prefs.get("genero_preferido")
        query = {
            "_id": {"$ne": user_id},
            "genero": gender_filter if gender_filter else {"$exists": True},
        }
        
        # Get candidates
        candidates = await self.db["user_profiles"].find(query).skip(skip).limit(limit).to_list(limit)
        
        matches = []
        for candidate in candidates:
            candidate_location = await self.get_user_location(str(candidate["_id"]))
            score, reasons = await self.calculate_compatibility(
                user, candidate, location, candidate_location
            )
            
            if score >= self.min_score:
                matches.append({
                    "user_id": str(candidate["_id"]),
                    "score": score,
                    "reasons": reasons,
                })
        
        # Sort by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches
    
    async def create_match(
        self,
        user_a_id: str,
        user_b_id: str,
    ) -> Optional[dict]:
        """
        Create a match between two users
        """
        # Get both users
        user_a = await self.get_user_profile(user_a_id)
        user_b = await self.get_user_profile(user_b_id)
        
        if not user_a or not user_b:
            logger.error(f"One or both users not found: {user_a_id}, {user_b_id}")
            return None
        
        # Get locations
        loc_a = await self.get_user_location(user_a_id)
        loc_b = await self.get_user_location(user_b_id)
        
        # Calculate compatibility
        score, reasons = await self.calculate_compatibility(user_a, user_b, loc_a, loc_b)
        
        if score < self.min_score:
            logger.warning(f"Compatibility score too low: {score}")
            return None
        
        # Create match document
        match_doc = {
            "user_a_id": user_a_id,
            "user_b_id": user_b_id,
            "status": MatchStatus.PENDING.value,
            "compatibility_score": score,
            "reasons": reasons,
            "unlock_level": 0,  
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "expires_at": utc_now() + timedelta(days=7),
            "metadata": {
                "initiated_by": user_a_id,
            },
        }
        
        try:
            result = await self.db["matches"].insert_one(match_doc)
            match_doc["_id"] = result.inserted_id
            return match_doc
        except Exception as e:
            logger.error(f"Error creating match: {e}")
            return None
