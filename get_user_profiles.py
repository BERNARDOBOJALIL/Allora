#!/usr/bin/env python3
"""
Script para recuperar y mostrar los perfiles de usuarios existentes
Conecta directamente a MongoDB sin necesidad de los servicios corriendo
"""

import asyncio
import json
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError


async def get_user_profiles():
    """
    Conecta a MongoDB y recupera todos los perfiles de usuarios
    Intenta multiples configuraciones de conexion
    """
    # Configuraciones de conexion a intentar
    mongo_configs = [
        ("mongodb://root:password@localhost:27017/allora_auth?authSource=admin", "root:password en admin"),
        ("mongodb://localhost:27017/allora_auth?authSource=admin", "Sin auth, auth en admin"),
        ("mongodb://root:password@localhost:27017/allora_auth", "Con root:password"),
        ("mongodb://localhost:27017/allora_auth", "Sin autenticacion"),
    ]
    
    MONGO_DB = "allora_auth"
    client = None
    db = None
    
    try:
        # Intentar conectar con diferentes configuraciones
        for mongo_uri, description in mongo_configs:
            try:
                print(f"[*] Intentando: {description}...")
                temp_client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=3000)
                temp_db = temp_client[MONGO_DB]
                
                # Intentar una operacion de lectura para verificar autenticacion real
                await temp_db.users.count_documents({})
                
                print(f"[OK] Conexion exitosa: {description}\n")
                client = temp_client
                db = temp_db
                break
            except Exception as e:
                error_name = type(e).__name__
                print(f"    [X] {error_name}")
                if temp_client:
                    temp_client.close()
                continue
        
        if client is None:
            raise Exception("No se pudo conectar a MongoDB con ninguna configuracion")
        
        # Recuperar todos los usuarios activos
        users = await db.users.find({"is_active": True}).to_list(None)
        print(f"[INFO] Encontrados {len(users)} usuarios activos\n")
        
        if not users:
            print("Sin usuarios activos en la base de datos.")
            return
        
        # Para cada usuario, recuperar su perfil y construir el perfil combinado
        results = []
        for user in users:
            user_id = str(user["_id"])
            
            # Recuperar perfil del usuario
            profile = await db.profiles.find_one({"user_id": user_id}) or {}
            
            # Construir match_profile (como lo hace el auth-service)
            pm = profile.get("profile_memory") or {}
            pref = profile.get("preference_memory") or {}
            
            match_profile = {
                "id": user_id,
                "nombre": user.get("nombre"),
                "email": user.get("email"),
                "edad": pm.get("edad") or pm.get("age"),
                "genero": pm.get("genero") or pm.get("gender"),
                "bio": pm.get("bio") or pm.get("biography"),
                "fotos": pm.get("fotos") or pm.get("photos") or [],
                "intereses": pm.get("intereses") or pm.get("interests") or pm.get("hobbies") or [],
                "ubicacion": pm.get("ubicacion") or pm.get("location") or {},
                "preferencias": {
                    "edad_minima": pref.get("edad_minima") or pref.get("min_age") or 18,
                    "edad_maxima": pref.get("edad_maxima") or pref.get("max_age") or 65,
                    "distancia_maxima_km": pref.get("distancia_maxima_km") or pref.get("max_distance_km") or 50,
                    "genero_preferido": pref.get("genero_preferido") or pref.get("preferred_gender"),
                },
            }
            
            results.append(match_profile)
            
            # Mostrar informacion del usuario
            print(f"[USER] {user.get('nombre')} ({user.get('email')})")
            print(f"       ID: {user_id}")
            print(f"       Edad: {match_profile['edad']}")
            print(f"       Genero: {match_profile['genero']}")
            print(f"       Bio: {match_profile['bio']}")
            intereses_str = ', '.join(match_profile['intereses']) if match_profile['intereses'] else 'No especificados'
            print(f"       Intereses: {intereses_str}")
            print(f"       Ubicacion: {match_profile['ubicacion']}")
            print(f"       Preferencias: edad {match_profile['preferencias']['edad_minima']}-{match_profile['preferencias']['edad_maxima']}, genero {match_profile['preferencias']['genero_preferido']}, distancia {match_profile['preferencias']['distancia_maxima_km']}km")
            print()
        
        # Mostrar resumen en JSON
        print("\n" + "="*80)
        print("[RESUMEN] TODOS LOS PERFILES EN JSON:")
        print("="*80)
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
        
        # Mostrar estadisticas
        print("\n" + "="*80)
        print("[ESTADISTICAS]:")
        print("="*80)
        print(f"Total de usuarios: {len(results)}")
        usuarios_con_perfil_completo = sum(1 for r in results if r.get('edad') and r.get('genero'))
        print(f"Usuarios con perfil completo: {usuarios_con_perfil_completo}")
        usuarios_con_intereses = sum(1 for r in results if r.get('intereses'))
        print(f"Usuarios con intereses: {usuarios_con_intereses}")
        usuarios_con_ubicacion = sum(1 for r in results if r.get('ubicacion'))
        print(f"Usuarios con ubicacion: {usuarios_con_ubicacion}")
        
        client.close()
        
    except ServerSelectionTimeoutError:
        print("[ERROR] No se puede conectar a MongoDB en localhost:27017")
        print("Asegurate de que:")
        print("  1. MongoDB esta corriendo (docker-compose up)")
        print("  2. Las credenciales son correctas (root:password)")
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("[*] Recuperando perfiles de usuarios desde MongoDB...\n")
    asyncio.run(get_user_profiles())
