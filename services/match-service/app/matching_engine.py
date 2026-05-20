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
        self.profile_agent_url = settings.profile_agent_url
        self.max_distance = settings.max_distance_km
        self.min_score = settings.min_compatibility_score

    @staticmethod
    def _normalize_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @staticmethod
    def _merge_unique_strings(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for item in group:
                key = item.lower()
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
        return merged

    async def get_agent_profile(self, user_id: str) -> Optional[dict]:
        """Get user profile memory from profile-agent."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.profile_agent_url}/profile/{user_id}",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.warning(f"Error fetching profile-agent memory for {user_id}: {e}")
        return None

    def enrich_profile_with_agent_memory(self, base_profile: dict, agent_payload: Optional[dict]) -> dict:
        """Merge profile-agent memory into auth profile shape expected by matching."""
        if not agent_payload:
            return base_profile

        profile = dict(base_profile)
        profile_memory = agent_payload.get("profile_memory") or {}
        preference_memory = agent_payload.get("preference_memory") or {}

        edad = profile_memory.get("edad") or profile_memory.get("age")
        genero = profile_memory.get("genero") or profile_memory.get("gender")
        bio = profile_memory.get("bio") or profile_memory.get("biography") or profile_memory.get("vibe_summary")
        fotos = self._normalize_list(profile_memory.get("fotos") or profile_memory.get("photos"))

        soft_interests = self._merge_unique_strings(
            self._normalize_list(profile_memory.get("intereses") or profile_memory.get("interests")),
            self._normalize_list(profile_memory.get("hobbies")),
            self._normalize_list(profile_memory.get("favorite_environments")),
            self._normalize_list(profile_memory.get("personality_traits")),
        )

        existing_interests = self._normalize_list(profile.get("intereses"))
        merged_interests = self._merge_unique_strings(existing_interests, soft_interests)

        existing_prefs = profile.get("preferencias") or {}
        merged_preferences = {
            "edad_minima": (
                preference_memory.get("edad_minima")
                or preference_memory.get("min_age")
                or existing_prefs.get("edad_minima")
                or 18
            ),
            "edad_maxima": (
                preference_memory.get("edad_maxima")
                or preference_memory.get("max_age")
                or existing_prefs.get("edad_maxima")
                or 65
            ),
            "distancia_maxima_km": (
                preference_memory.get("distancia_maxima_km")
                or preference_memory.get("max_distance_km")
                or existing_prefs.get("distancia_maxima_km")
                or self.max_distance
            ),
            "genero_preferido": (
                preference_memory.get("genero_preferido")
                or preference_memory.get("preferred_gender")
                or existing_prefs.get("genero_preferido")
            ),
        }

        location = profile_memory.get("ubicacion") or profile_memory.get("location") or profile.get("ubicacion")

        if edad is not None:
            profile["edad"] = edad
        if genero:
            profile["genero"] = genero
        if bio:
            profile["bio"] = bio
        if fotos:
            profile["fotos"] = fotos
        if merged_interests:
            profile["intereses"] = merged_interests
        if location:
            profile["ubicacion"] = location

        profile["preferencias"] = merged_preferences
        profile["agent_profile_completion"] = agent_payload.get("profile_completion")
        profile["social_style"] = profile_memory.get("social_style")
        profile["vibe_summary"] = profile_memory.get("vibe_summary")
        profile["emotional_style"] = profile_memory.get("emotional_style")
        profile["dislikes"] = self._normalize_list(profile_memory.get("dislikes"))

        return profile
    
    async def get_user_profile(self, user_id: str) -> Optional[dict]:
        """Get user profile from auth service and enrich it with profile-agent memory."""
        base_profile: Optional[dict] = None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.auth_service_url}/users/{user_id}",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    base_profile = response.json()
        except Exception as e:
            logger.error(f"Error fetching user profile {user_id}: {e}")

        if not base_profile:
            return None

        agent_profile = await self.get_agent_profile(user_id)
        return self.enrich_profile_with_agent_memory(base_profile, agent_profile)

    async def list_all_user_profiles(self) -> list[dict]:
        """List all active user profiles from auth service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.auth_service_url}/users",
                    timeout=10.0,
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.error(f"Error listing user profiles: {e}")
        return []

    async def get_user_location(self, user_id: str, profile: Optional[dict] = None) -> Optional[dict]:
        """Get user location from location service or fallback to profile location"""
        if profile:
            location = profile.get("ubicacion")
            if location and location.get("lat") is not None and location.get("lng") is not None:
                return location

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.location_service_url}/api/v1/locations/{user_id}",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.warning(f"Error fetching user location {user_id}: {e}")
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

        # Soft-profile compatibility signals from profile-agent memory.
        style_a = (user_a.get("social_style") or "").strip().lower()
        style_b = (user_b.get("social_style") or "").strip().lower()
        if style_a and style_b and style_a == style_b:
            reasons.append("Compatible social style")

        vibe_a = (user_a.get("vibe_summary") or "").strip()
        vibe_b = (user_b.get("vibe_summary") or "").strip()
        if vibe_a and vibe_b:
            reasons.append("Both users have rich profile-agent memory")
        
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
        
        # Get candidate profiles from auth service
        candidates = await self.list_all_user_profiles()
        candidates = [
            candidate for candidate in candidates
            if str(candidate.get("id")) != user_id
        ]

        if gender_filter:
            candidates = [
                candidate for candidate in candidates
                if str(candidate.get("genero", "")).lower() == str(gender_filter).lower()
            ]

        candidates = candidates[skip: skip + limit]

        matches = []
        for candidate in candidates:
            candidate_id = candidate.get("id")
            if not candidate_id:
                logger.warning(f"Candidate without id: {candidate}")
                continue
            candidate_id = str(candidate_id)
            
            candidate_profile = await self.get_user_profile(candidate_id)
            if not candidate_profile:
                logger.warning(f"Could not fetch profile for candidate {candidate_id}")
                continue
            candidate = candidate_profile

            candidate_location = await self.get_user_location(
                candidate_id,
                profile=candidate,
            )
            try:
                score, reasons = await self.calculate_compatibility(
                    user, candidate, location, candidate_location
                )

                if score >= self.min_score:
                    matches.append({
                        "user_id": candidate_id,
                        "score": score,
                        "reasons": reasons,
                    })
            except Exception as e:
                logger.error(f"Error calculating compatibility for candidate {candidate_id}: {e}")
                continue

        # Sort by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches
    
    async def create_match(
        self,
        user_a_id: str,
        user_b_id: str,
        bypass_score: bool = False,
    ) -> Optional[dict]:
        """
        Create a match between two users.
        bypass_score=True skips the min_score gate (used for direct radar requests).
        """
        # Get both users - fall back to minimal stub if profile service is unreachable
        user_a = await self.get_user_profile(user_a_id)
        user_b = await self.get_user_profile(user_b_id)

        if not user_a:
            logger.warning(f"Profile not found for user_a {user_a_id}, using stub")
            user_a = {"id": user_a_id, "edad": 0, "genero": "", "intereses": [], "preferencias": {}}
        if not user_b:
            logger.warning(f"Profile not found for user_b {user_b_id}, using stub")
            user_b = {"id": user_b_id, "edad": 0, "genero": "", "intereses": [], "preferencias": {}}

        # Get locations
        loc_a = await self.get_user_location(user_a_id)
        loc_b = await self.get_user_location(user_b_id)

        # Calculate compatibility
        try:
            score, reasons = await self.calculate_compatibility(user_a, user_b, loc_a, loc_b)
        except Exception as e:
            logger.warning(f"Compatibility calculation failed, defaulting score to 0: {e}")
            score, reasons = 0.0, ["Compatibility could not be calculated"]

        if not bypass_score and score < self.min_score:
            logger.warning(f"Compatibility score too low: {score}")
            return None
        
        # Create match document
        match_doc = {
            "user_a_id": user_a_id,
            "user_b_id": user_b_id,
            "status": MatchStatus.PENDING.value,
            "compatibility_score": score,
            "reasons": reasons,
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