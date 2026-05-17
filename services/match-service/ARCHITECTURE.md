# Arquitectura Match Service

## Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway                              │
│                     (puerto 8000)                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │        Match Service                     │
        │        (puerto 8002)                     │
        │                                          │
        │  ┌──────────────────────────────────┐   │
        │  │   FastAPI Application             │   │
        │  │   - /health                       │   │
        │  │   - /matches (CRUD)               │   │
        │  │   - /users/{id}/matches           │   │
        │  │   - /compatibility                │   │
        │  └──────────────────────────────────┘   │
        │            │         │                  │
        │            ▼         ▼                  │
        │  ┌─────────────┐  ┌──────────────────┐  │
        │  │ Matching    │  │ Database Layer   │  │
        │  │ Engine      │  │ (Motor + Motor)  │  │
        │  │             │  │                  │  │
        │  │ • Haversine │  │ • MongoDB        │  │
        │  │ • Score     │  │ • Indexes        │  │
        │  │ • Filter    │  │ • Collections    │  │
        │  └─────────────┘  └──────────────────┘  │
        │            │              │             │
        └────────────┼──────────────┼─────────────┘
                     │              │
        ┌────────────▼──────┐  ┌────▼──────────────┐
        │  Auth Service     │  │  MongoDB          │
        │  (puerto 8000)    │  │  (puerto 27017)   │
        │                   │  │                   │
        │ • /users/{id}     │  │ • matches         │
        │ • Profiles        │  │ • user_profiles   │
        └───────────────────┘  └───────────────────┘

        ┌───────────────────────────────────────────┐
        │  Location Service                         │
        │  (puerto 8003)                            │
        │                                           │
        │ • /api/v1/locations/{user_id}             │
        │ • Coordenadas en tiempo real               │
        └───────────────────────────────────────────┘
```

## Flujo de Datos

### 1. Crear un Match

```
Usuario A quiere hacer match con Usuario B
        │
        ▼
POST /matches
{user_a_id, user_b_id}
        │
        ▼
┌─────────────────────────────┐
│ 1. Obtener perfil Usuario A │──→ Auth Service
│ 2. Obtener perfil Usuario B │──→ Auth Service
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 3. Obtener ubicación A      │──→ Location Service
│ 4. Obtener ubicación B      │──→ Location Service
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ Matching Engine             │
│ • Validar edad              │
│ • Validar género            │
│ • Calcular distancia        │
│ • Contar intereses comunes  │
│ • Calcular score total      │
└─────────────────────────────┘
        │
        ▼
    Score >= 50?
    ├─ SÍ ──→ Crear documento en MongoDB
    │        Status: PENDING
    │        Expires: +7 días
    │        Retornar Match
    │
    └─ NO ──→ Retornar error
             "Compatibilidad insuficiente"
```

### 2. Buscar Matches Potenciales

```
GET /users/{user_id}/matches?limit=10
        │
        ▼
┌─────────────────────────────────────┐
│ 1. Obtener perfil del usuario       │──→ Auth Service
│ 2. Obtener ubicación actual         │──→ Location Service
│ 3. Leer preferencias                │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│ Buscar candidatos en MongoDB        │
│ Filtros:                            │
│ • Género preferido                  │
│ • Edad dentro del rango             │
│ • Dentro del radio de distancia     │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│ Para cada candidato:                │
│ 1. Obtener su ubicación             │
│ 2. Calcular compatibilidad          │
│ 3. Si score >= 50:                  │
│    - Agregar a resultados           │
│    - Guardar score y razones        │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│ Ordenar por score descendente       │
│ Limitar a 10 resultados             │
│ Retornar al usuario                 │
└─────────────────────────────────────┘
```

## Estructura de Clases

```python
# Config
class Settings:
    - mongodb_url
    - mongodb_db
    - auth_service_url
    - location_service_url
    - max_distance_km
    - min_compatibility_score

# Models
class MatchStatus(Enum):
    - PENDING
    - ACCEPTED
    - REJECTED
    - EXPIRED

# Matching Engine
class MatchingEngine:
    - get_user_profile(user_id)
    - get_user_location(user_id)
    - calculate_compatibility(user_a, user_b, loc_a, loc_b)
    - find_matches(user_id, limit, skip)
    - create_match(user_a_id, user_b_id)
    - haversine_distance(lat1, lon1, lat2, lon2)

# Schemas (Pydantic)
- UserPreferencesSchema
- UserProfileSchema
- MatchResponse
- MatchCreateRequest
- MatchUpdateRequest
- MatchCompatibilityRequest
- MatchCompatibilityResponse
```

## Índices MongoDB Optimizados

```javascript
// Para búsqueda por usuario
db.matches.createIndex({ user_a_id: 1 })
db.matches.createIndex({ user_b_id: 1 })

// Para búsqueda de matches únicos
db.matches.createIndex(
    { user_a_id: 1, user_b_id: 1 },
    { unique: true }
)

// Para filtrado por estado
db.matches.createIndex({ status: 1 })

// Para limpieza de expirados
db.matches.createIndex({ expires_at: 1 })

// Para listados ordenados
db.matches.createIndex({ created_at: -1 })

// Perfil de usuario
db.user_profiles.createIndex({ user_id: 1 }, { unique: true })
db.user_profiles.createIndex({ genero: 1 })
db.user_profiles.createIndex({ intereses: 1 })
```

## Algoritmo de Compatibilidad Detallado

```
Total Score = 0

├─ 1. Validar edad (0 o 25 puntos)
│  ├─ edad_usuario_a dentro de rango preferencias usuario_b?
│  ├─ edad_usuario_b dentro de rango preferencias usuario_a?
│  └─ SI → +25 puntos | NO → Score final = 0
│
├─ 2. Validar género (0 o 20 puntos)
│  ├─ género_usuario_a matches preferencia usuario_b?
│  ├─ género_usuario_b matches preferencia usuario_a?
│  └─ SI → +20 puntos | NO → Score final = 0
│
├─ 3. Proximidad geográfica (0-25 puntos)
│  ├─ Calcular distancia Haversine
│  ├─ distance <= max_distance_a AND distance <= max_distance_b?
│  ├─ SI → +25 * (1 - distance/max_distance) puntos
│  └─ NO → Score final = 0
│
└─ 4. Intereses comunes (0-30 puntos)
   ├─ Contar intereses en común
   ├─ puntos = min(30, common_interests * 5)
   └─ +puntos

Final Score = min(100, Total Score)
Match válido SI Final Score >= 50
```

## Flujo de Autenticación

```
HTTP Request
     │
     ▼
┌──────────────────────────┐
│ API Gateway              │
│ Verifica JWT Token       │
└──────────────────────────┘
     │
     ▼
  Válido?
  ├─ SÍ → Pasar user_id a Match Service
  └─ NO → Retornar 401 Unauthorized
```

## Ciclo de Vida de un Match

```
┌────────────────────────────────────────────────────┐
│                  PENDING                           │
│   Estado: Esperando respuesta del usuario B        │
│   TTL: 7 días                                      │
└──────────────────────────────────────────────────┐
                        │
         ┌──────────────┴──────────────┐
         │                             │
    Usuario B                   Expira
    responde                   automático
         │                             │
         ▼                             ▼
    ┌─────────────────┐        ┌──────────────┐
    │   ACCEPTED      │        │   EXPIRED    │
    │   o             │        │   (arquivado)│
    │   REJECTED      │        └──────────────┘
    └─────────────────┘
```

---

**Generado**: Mayo 16, 2024
**Versión**: 1.0.0
