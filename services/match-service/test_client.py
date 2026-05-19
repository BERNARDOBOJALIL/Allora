"""
Ejemplo de cliente para el Match Service
Demuestra cómo usar los endpoints del servicio de matching
"""

import asyncio
import httpx
from typing import Optional


class MatchServiceClient:
    def __init__(self, base_url: str = "http://localhost:8002"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def health_check(self) -> dict:
        """Verificar salud del servicio"""
        response = await self.client.get(f"{self.base_url}/health")
        return response.json()
    
    async def get_potential_matches(
        self,
        user_id: str,
        limit: int = 10,
        skip: int = 0,
    ) -> dict:
        """Obtener matches potenciales para un usuario"""
        response = await self.client.get(
            f"{self.base_url}/users/{user_id}/matches",
            params={"limit": limit, "skip": skip},
        )
        return response.json()
    
    async def calculate_compatibility(
        self,
        user_a_id: str,
        user_b_id: str,
    ) -> dict:
        """Calcular compatibilidad entre dos usuarios"""
        response = await self.client.post(
            f"{self.base_url}/compatibility",
            json={
                "user_a_id": user_a_id,
                "user_b_id": user_b_id,
            },
        )
        return response.json()
    
    async def create_match(
        self,
        user_a_id: str,
        user_b_id: str,
    ) -> dict:
        """Crear un match entre dos usuarios"""
        response = await self.client.post(
            f"{self.base_url}/matches",
            json={
                "user_a_id": user_a_id,
                "user_b_id": user_b_id,
            },
        )
        return response.json()
    
    async def get_match(self, match_id: str) -> dict:
        """Obtener detalles de un match"""
        response = await self.client.get(f"{self.base_url}/matches/{match_id}")
        return response.json()
    
    async def get_user_matches(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        skip: int = 0,
    ) -> dict:
        """Obtener todos los matches de un usuario"""
        params = {"limit": limit, "skip": skip}
        if status:
            params["status"] = status
        
        response = await self.client.get(
            f"{self.base_url}/users/{user_id}/all-matches",
            params=params,
        )
        return response.json()
    
    async def update_match_status(
        self,
        match_id: str,
        status: str,  # PENDING, ACCEPTED, REJECTED, EXPIRED
    ) -> dict:
        """Actualizar el estado de un match"""
        response = await self.client.put(
            f"{self.base_url}/matches/{match_id}",
            json={"status": status},
        )
        return response.json()
    
    async def delete_match(self, match_id: str) -> None:
        """Eliminar un match"""
        response = await self.client.delete(f"{self.base_url}/matches/{match_id}")
        response.raise_for_status()
    
    async def close(self):
        """Cerrar cliente"""
        await self.client.aclose()


async def main():
    """Ejemplo de uso del cliente"""
    client = MatchServiceClient()
    
    try:
        # 1. Verificar salud del servicio
        print("1. Health Check:")
        health = await client.health_check()
        print(f"   {health}\n")
        
        # 2. Calcular compatibilidad entre dos usuarios
        print("2. Calculate Compatibility:")
        compat = await client.calculate_compatibility(
            user_a_id="507f1f77bcf86cd799439011",  # Reemplazar con IDs reales
            user_b_id="507f1f77bcf86cd799439012",
        )
        print(f"   Score: {compat.get('score', 'N/A')}")
        print(f"   Reasons: {compat.get('reasons', [])}\n")
        
        # 3. Crear un match
        print("3. Create Match:")
        match = await client.create_match(
            user_a_id="507f1f77bcf86cd799439011",
            user_b_id="507f1f77bcf86cd799439012",
        )
        if "id" in match:
            match_id = match["id"]
            print(f"   Match created: {match_id}")
            print(f"   Status: {match.get('status')}")
            print(f"   Score: {match.get('compatibility_score')}\n")
            
            # 4. Obtener detalles del match
            print("4. Get Match Details:")
            match_details = await client.get_match(match_id)
            print(f"   {match_details}\n")
            
            # 5. Actualizar estado del match
            print("5. Update Match Status:")
            updated = await client.update_match_status(match_id, "ACCEPTED")
            print(f"   New status: {updated.get('status')}\n")
            
            # 6. Obtener todos los matches de un usuario
            print("6. Get User Matches:")
            user_matches = await client.get_user_matches(
                user_id="507f1f77bcf86cd799439011"
            )
            print(f"   Total matches: {user_matches.get('total')}\n")
        else:
            print(f"   Error: {match}\n")
        
        # 7. Obtener matches potenciales
        print("7. Get Potential Matches:")
        potential = await client.get_potential_matches(
            user_id="507f1f77bcf86cd799439011",
            limit=5,
        )
        print(f"   Total: {potential.get('total')}")
        print(f"   Matches: {len(potential.get('matches', []))}\n")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
