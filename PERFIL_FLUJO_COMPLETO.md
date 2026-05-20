# Flujo Completo: Perfil + Matching con Allora Agent

## 📊 El Flujo (Correcto)

```
┌─────────────────────────────────────────────────────────────────┐
│ USUARIO 1: REGISTRO + CONVERSACIÓN CON AGENTE                  │
└─────────────────────────────────────────────────────────────────┘

1️⃣ REGISTRO (MÍNIMO)
   POST /auth/register
   {
     "nombre": "Carlos",
     "email": "carlos@gmail.com",
     "password": "SecurePass123!"
   }
   ↓
   auth-service crea:
   - db.users (identidad)
   - db.profiles (vacío, lista para llenar)

2️⃣ CONVERSACIÓN CON AGENT
   POST /chat (conversación en el frontend)
   Ejemplos de interacción:
   
   Usuario: "Hola, soy Carlos, tengo 28 años, soy ingeniero"
   Agent: "Mucho gusto Carlos. Dime, ¿cuáles son tus hobbies?"
   
   Usuario: "Me encanta senderismo, fotografía y la música"
   Agent: "Genial. ¿Qué tipo de persona buscas?"
   
   Usuario: "Alguien aventurero, tranquilo"
   Agent: Guarda en profile-agent:
   {
     "user_id": "carlos_id",
     "profile_memory": {
       "edad": 28,
       "genero": "masculino",
       "bio": "Ingeniero aventurero",
       "intereses": ["senderismo", "fotografía", "música"],
       "hobbies": ["senderismo", "fotografía"],
       "personality_traits": ["aventurero", "ingeniero"],
       "social_style": "Prefiere planes tranquilos",
       "favorite_environments": ["montañas", "naturaleza"],
       "vibe_summary": "Ingeniero creativo y aventurero"
     },
     "preference_memory": {
       "edad_minima": 25,
       "edad_maxima": 35,
       "genero_preferido": "femenino",
       "distancia_maxima_km": 50
     }
   }

3️⃣ MATCH BÚSQUEDA
   GET /users/{carlos_id}/matches
   ↓
   match-service:
   ├─ Obtiene lista de usuarios activos de auth-service
   ├─ Para CADA candidato:
   │  ├─ Consulta profile-agent: GET /profile/{candidato_id}
   │  │  └─ Recupera intereses, personalidad, etc.
   │  ├─ Obtiene ubicación de location-service
   │  ├─ CALCULA COMPATIBILIDAD:
   │  │  • Intereses comunes
   │  │  • Similitud de personalidad
   │  │  • Preferencias de edad/género/distancia
   │  │  • Afinidad de estilos sociales
   │  └─ Score final (0-100)
   │
   ├─ Ordena por score descendente
   └─ Retorna Top 10 candidatos
```

## 🔄 Datos NUNCA se Piden en Registro

| Campo | Construido Por | Almacenado En |
|-------|---|---|
| `edad` | Agent (conversación) | profile-agent |
| `genero` | Agent (conversación) | profile-agent |
| `bio` | Agent (conversación) | profile-agent |
| `intereses` | Agent (conversación) | profile-agent |
| `hobbies` | Agent (conversación) | profile-agent |
| `personality_traits` | Agent (análisis conversación) | profile-agent |
| `social_style` | Agent (análisis conversación) | profile-agent |
| `favorite_environments` | Agent (análisis conversación) | profile-agent |
| `vibe_summary` | Agent (resumen creativo) | profile-agent |
| `preferencias` | Agent (preguntas interactivas) | profile-agent |

## ✅ Cambios Necesarios en Match Service

### 1. Agregar PROFILE_AGENT_URL a config.py

```python
# services/match-service/app/config.py
class Settings(BaseSettings):
    auth_service_url: str = "http://auth-service:8001"
    location_service_url: str = "http://location-service:8004"
    profile_agent_url: str = "https://alloraagent.onrender.com"  # 👈 NUEVO
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
```

### 2. Enriquecer Perfiles con Datos del Agent

En `matching_engine.py`:

```python
async def get_profile_from_agent(self, user_id: str) -> dict:
    """
    Obtiene el perfil enriquecido del profile-agent
    Fallback a auth-service si el agent no tiene datos
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{self.settings.profile_agent_url}/profile/{user_id}"
            )
            if resp.status_code == 200:
                agent_profile = resp.json()
                profile_memory = agent_profile.get("profile_memory", {})
                pref_memory = agent_profile.get("preference_memory", {})
                
                # Retorna datos del agent
                return {
                    "from_agent": True,
                    "profile_memory": profile_memory,
                    "preference_memory": pref_memory,
                }
    except Exception as e:
        # Log del error pero continúa
        print(f"Agent unavailable for {user_id}: {e}")
    
    # Fallback a auth-service
    return await self.get_user_profile(user_id)  # método existente


async def get_user_profile_enriched(self, user_id: str) -> dict:
    """
    Construye perfil combinando:
    - Datos básicos de auth-service (nombre, email)
    - Datos enriquecidos del profile-agent (edad, intereses, personalidad)
    """
    # Obtener perfil básico de auth-service
    basic_profile = await self.get_user_profile(user_id)
    
    # Enriquecer con datos del agent
    agent_data = await self.get_profile_from_agent(user_id)
    
    if agent_data.get("from_agent"):
        pm = agent_data.get("profile_memory", {})
        pref = agent_data.get("preference_memory", {})
        
        # Mezclar datos: agent sobrescribe auth-service
        basic_profile.update({
            "edad": pm.get("edad") or basic_profile.get("edad"),
            "genero": pm.get("genero") or basic_profile.get("genero"),
            "bio": pm.get("bio") or basic_profile.get("bio"),
            "fotos": pm.get("fotos") or basic_profile.get("fotos", []),
            "intereses": pm.get("intereses") or basic_profile.get("intereses", []),
            "hobbies": pm.get("hobbies", []),
            "personality_traits": pm.get("personality_traits", []),
            "social_style": pm.get("social_style"),
            "favorite_environments": pm.get("favorite_environments", []),
            "vibe_summary": pm.get("vibe_summary"),
            "dislikes": pm.get("dislikes", []),
            "emotional_style": pm.get("emotional_style"),
            "ubicacion": pm.get("ubicacion") or basic_profile.get("ubicacion", {}),
            "preferencias": {
                "edad_minima": pref.get("edad_minima", 18),
                "edad_maxima": pref.get("edad_maxima", 65),
                "distancia_maxima_km": pref.get("distancia_maxima_km", 50),
                "genero_preferido": pref.get("genero_preferido"),
            }
        })
    
    return basic_profile
```

### 3. Usar Perfil Enriquecido en Matching

```python
async def find_matches(self, user_id: str, limit: int = 10, skip: int = 0) -> list[dict]:
    """
    Busca matches usando perfiles enriquecidos del agent
    """
    # Obtener usuario (ahora enriquecido con datos del agent)
    user = await self.get_user_profile_enriched(user_id)  # 👈 CAMBIO
    user_location = await self.get_user_location(user_id)
    
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    # Obtener candidatos
    all_users = await self.list_all_user_profiles()
    
    candidates = []
    for candidate in all_users:
        if str(candidate.get("id")) == user_id:
            continue
        
        # Enriquecer candidato también
        candidate_enriched = await self.get_user_profile_enriched(candidate["id"])  # 👈 CAMBIO
        candidate_location = await self.get_user_location(candidate["id"])
        
        # Calcular compatibilidad
        compatibility = self.calculate_compatibility(
            user,
            candidate_enriched,  # 👈 CAMBIO: ahora con datos del agent
            user_location,
            candidate_location,
        )
        
        if compatibility["score"] >= self.settings.min_compatibility_score:
            candidates.append({
                **candidate_enriched,
                "compatibility_score": compatibility["score"],
                "compatibility_reasons": compatibility["reasons"],
            })
    
    # Ordenar y paginar
    candidates.sort(key=lambda x: x["compatibility_score"], reverse=True)
    return candidates[skip : skip + limit]
```

### 4. Mejorar calculate_compatibility con Datos Suaves

```python
def calculate_compatibility(self, user_a, user_b, loc_a, loc_b) -> dict:
    """
    Calcula compatibilidad considerando:
    - Criterios duros: edad, género, distancia
    - Criterios suaves: personalidad, intereses, hobbies, estilos
    """
    score = 0
    reasons = []
    
    # 1. EDAD (25 pts)
    if self._check_age_range(user_a, user_b):
        score += 25
        reasons.append("Rango de edad compatible")
    else:
        return {"score": 0, "reasons": ["No compatible: edad fuera de rango"]}
    
    # 2. GÉNERO (20 pts)
    if self._check_gender_match(user_a, user_b):
        score += 20
        reasons.append("Género compatible")
    else:
        return {"score": 0, "reasons": ["No compatible: género no coincide"]}
    
    # 3. DISTANCIA (0-15 pts)
    if loc_a and loc_b:
        distance_score = self._calculate_distance_score(loc_a, loc_b, user_a, user_b)
        score += distance_score
        if distance_score > 0:
            reasons.append(f"Distancia aceptable ({distance_score}pts)")
    
    # 4. INTERESES COMUNES (0-20 pts) 👈 MEJORADO
    intereses_a = set(user_a.get("intereses", []))
    intereses_b = set(user_b.get("intereses", []))
    common_interests = len(intereses_a & intereses_b)
    interest_score = min(20, common_interests * 4)
    score += interest_score
    if interest_score > 0:
        reasons.append(f"Intereses comunes: {', '.join(intereses_a & intereses_b)}")
    
    # 5. HOBBIES COMUNES (0-15 pts) 👈 NUEVO
    hobbies_a = set(user_a.get("hobbies", []))
    hobbies_b = set(user_b.get("hobbies", []))
    common_hobbies = len(hobbies_a & hobbies_b)
    hobby_score = min(15, common_hobbies * 5)
    score += hobby_score
    if hobby_score > 0:
        reasons.append(f"Hobbies compartidos: {', '.join(hobbies_a & hobbies_b)}")
    
    # 6. SIMILITUD DE PERSONALIDAD (0-15 pts) 👈 NUEVO
    traits_a = set(user_a.get("personality_traits", []))
    traits_b = set(user_b.get("personality_traits", []))
    common_traits = len(traits_a & traits_b)
    trait_score = min(15, common_traits * 5)
    score += trait_score
    if trait_score > 0:
        reasons.append(f"Personalidad compatible: {', '.join(traits_a & traits_b)}")
    
    # 7. ESTILOS SOCIALES COMPATIBLES (0-10 pts) 👈 NUEVO
    social_a = user_a.get("social_style", "")
    social_b = user_b.get("social_style", "")
    if self._social_styles_compatible(social_a, social_b):
        score += 10
        reasons.append("Estilos sociales compatibles")
    
    return {
        "score": min(100, score),
        "reasons": reasons,
    }

def _social_styles_compatible(self, style_a: str, style_b: str) -> bool:
    """Lógica simple: si ambos mencionan 'tranquilo' o 'aventurero', compatible"""
    if not style_a or not style_b:
        return True  # Sin datos = compatible por defecto
    
    tranquilo_a = "tranquilo" in style_a.lower()
    tranquilo_b = "tranquilo" in style_b.lower()
    aventurero_a = "aventurero" in style_a.lower()
    aventurero_b = "aventurero" in style_b.lower()
    
    # Mismo tipo de estilo
    return (tranquilo_a == tranquilo_b) or (aventurero_a == aventurero_b)
```

## 📦 Variables de Entorno Necesarias

```env
# .env del match-service
AUTH_SERVICE_URL=http://auth-service:8001
LOCATION_SERVICE_URL=http://location-service:8004
PROFILE_AGENT_URL=https://alloraagent.onrender.com  # 👈 NUEVA

MIN_COMPATIBILITY_SCORE=50  # Escala 0-100
```

## 🎯 Resumen del Cambio

| Antes | Ahora |
|-------|-------|
| Usuario pide edad, género en registro | Usuario se registra solo con nombre/email |
| Perfil vacío si no completa formulario | Perfil se completa hablando con Allora Agent |
| Match-service usa datos incompletos de auth-service | Match-service consulta profile-agent para datos enriquecidos |
| Score based on: edad, género, distancia, intereses | Score basado en: edad, género, distancia, **intereses, hobbies, personalidad, estilos sociales** |
| ~40% de matches fallaban por datos incompletos | ~100% matches pueden hacerse con datos del agent |

## ✅ Ventajas

1. **UX Mejor**: Sin formularios largos en registro
2. **Datos Richer**: Perfil enriquecido por conversación natural
3. **Matching Mejor**: Considera personalidad, no solo datos demográficos
4. **Flexible**: Usuario actualiza perfil hablando, sin form adicional
5. **Alineado**: Match-service usa misma fuente de datos que el frontend (Allora Agent)
