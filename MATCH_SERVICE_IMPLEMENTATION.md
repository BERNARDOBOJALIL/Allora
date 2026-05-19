# Match Service - Implementación Completada

## 📋 Resumen

Se ha creado el **Match Service** completo para la plataforma de citas **Allora**. Este servicio es responsable de:

1. **Cálculo de compatibilidad** entre usuarios
2. **Gestión de matches** (crear, actualizar, eliminar)
3. **Búsqueda de potenciales matches** basada en algoritmos inteligentes
4. **Recomendaciones** personalizadas

---

## 📁 Estructura de Archivos Creados

```
services/match-service/
├── app/
│   ├── __init__.py                 # Inicialización del paquete
│   ├── main.py                     # Aplicación FastAPI con endpoints
│   ├── config.py                   # Configuración del servicio
│   ├── models.py                   # Modelos de datos
│   ├── schemas.py                  # Esquemas Pydantic para validación
│   ├── database.py                 # Conexión a MongoDB
│   └── matching_engine.py          # Motor de algoritmo de matching
├── Dockerfile                       # Contenedor Docker
├── requirements.txt                 # Dependencias Python
├── README.md                        # Documentación detallada
├── test_client.py                  # Cliente Python para testing
└── examples.sh                      # Ejemplos de requests curl
```

---

## 🔧 Componentes Principales

### 1. **Matching Engine** (`matching_engine.py`)

**Algoritmo de compatibilidad:**
- ✅ Validación de edad y preferencias
- ✅ Compatibilidad de género
- ✅ Cálculo de distancia (Fórmula Haversine)
- ✅ Intereses comunes
- ✅ Score total: 0-100 puntos

**Criterios de puntuación:**
- Edad compatible: 25 puntos
- Género compatible: 20 puntos
- Proximidad geográfica: 25 puntos
- Intereses comunes: 30 puntos
- **Score mínimo requerido: 50 puntos**

### 2. **API Endpoints** (`main.py`)

#### Health Check
```
GET /health
```

#### Buscar Matches Potenciales
```
GET /users/{user_id}/matches?limit=10&skip=0
```
Retorna matches ordenados por compatibilidad

#### Calcular Compatibilidad
```
POST /compatibility
{
    "user_a_id": "userId1",
    "user_b_id": "userId2"
}
```

#### Crear Match
```
POST /matches
{
    "user_a_id": "userId1",
    "user_b_id": "userId2"
}
```

#### Obtener Match
```
GET /matches/{match_id}
```

#### Listar Matches del Usuario
```
GET /users/{user_id}/all-matches?status=PENDING&limit=20
```
Estados: `PENDING`, `ACCEPTED`, `REJECTED`, `EXPIRED`

#### Actualizar Status
```
PUT /matches/{match_id}
{
    "status": "ACCEPTED"
}
```

#### Eliminar Match
```
DELETE /matches/{match_id}
```

---

## 🗄️ Estructura de Base de Datos

### Colección: `matches`
```json
{
    "_id": ObjectId,
    "user_a_id": "string",
    "user_b_id": "string",
    "status": "PENDING|ACCEPTED|REJECTED|EXPIRED",
    "compatibility_score": 75.5,
    "reasons": [
        "Age preferences match",
        "Close proximity (15.2 km)",
        "Shared interests: travel, music"
    ],
    "created_at": "2024-05-16T10:30:00Z",
    "updated_at": "2024-05-16T10:30:00Z",
    "expires_at": "2024-05-23T10:30:00Z",
    "metadata": {}
}
```

**Índices:**
- user_a_id
- user_b_id
- (user_a_id, user_b_id) - Único
- status
- created_at
- expires_at

---

## 🔌 Integración con Otros Servicios

### Auth Service
- Obtiene perfiles de usuario
- Valida identidades

### Location Service
- Obtiene ubicaciones en tiempo real
- Calcula distancia entre usuarios

### API Gateway
- Enruta solicitudes al match-service
- Gestiona autenticación

---

## 🐳 Docker Configuration

### Configuración en `docker-compose.yml`

```yaml
match-service:
  build:
    context: ./services/match-service
    dockerfile: Dockerfile
  ports:
    - "8002:8002"
  environment:
    - MONGODB_URL=mongodb://root:password@mongodb:27017
    - MONGODB_DB=match_service
    - AUTH_SERVICE_URL=http://auth-service:8000
    - LOCATION_SERVICE_URL=http://location-service:8003
    - MAX_DISTANCE_KM=50.0
    - MIN_COMPATIBILITY_SCORE=0.5
  depends_on:
    - mongodb
    - auth-service
    - location-service
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
```

---

## 📦 Dependencias

```
fastapi==0.104.1          # Framework web asincrónico
uvicorn==0.24.0           # Servidor ASGI
motor==3.3.2              # Driver async MongoDB
pymongo==4.6.0            # Cliente MongoDB
pydantic==2.5.0           # Validación de datos
pydantic-settings==2.1.0  # Gestión de configuración
python-dotenv==1.0.0      # Manejo de variables de entorno
httpx==0.25.2             # Cliente HTTP async
aiohttp==3.9.1            # Cliente HTTP alternative
```

---

## 🧪 Testing

### Cliente Python (`test_client.py`)

```bash
python test_client.py
```

Proporciona ejemplos de cómo usar el servicio programáticamente.

### Ejemplos cURL (`examples.sh`)

```bash
bash examples.sh
```

Demuestra todos los endpoints disponibles.

---

## ⚙️ Variables de Configuración

En el archivo `.env`:

```env
# MongoDB
MONGODB_URL=mongodb://root:password@mongodb:27017
MONGODB_DB=match_service

# Servicios
AUTH_SERVICE_URL=http://auth-service:8000
LOCATION_SERVICE_URL=http://location-service:8003

# Matching
MAX_DISTANCE_KM=50.0
MIN_COMPATIBILITY_SCORE=0.5
LOG_LEVEL=INFO
```

---

## 🚀 Iniciar el Servicio

### Con Docker Compose (Recomendado)

```bash
docker-compose up --build match-service
```

### Localmente (Desarrollo)

```bash
cd services/match-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

---

## 📊 Flujo de Matching

```
┌─────────────────────────────────────────────────────────────┐
│                    Usuario A                                │
│  (perfil, ubicación, preferencias)                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Matching Engine       │
        │  ┌──────────────────┐  │
        │  │ 1. Edad          │  │
        │  │ 2. Género        │  │
        │  │ 3. Distancia     │  │
        │  │ 4. Intereses     │  │
        │  └──────────────────┘  │
        └────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Score > 50?           │
        │  ✓ Crear Match         │
        │  ✗ Rechazar            │
        └────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  MongoDB: Guardar      │
        │  - status: PENDING     │
        │  - score: XX.X         │
        │  - reasons: [...]      │
        └────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  Usuario B recibe notificación de potencial match          │
└──────────────────────────────────────────────────────────────┘
```

---

## ✅ Checklist de Implementación

- ✅ Estructura completa del proyecto
- ✅ Modelo de datos robusto
- ✅ Algoritmo de compatibilidad avanzado
- ✅ CRUD de matches
- ✅ Cálculo de distancia geográfica
- ✅ Integración con Auth Service
- ✅ Integración con Location Service
- ✅ Validación de datos con Pydantic
- ✅ Conexión asincrónica a MongoDB
- ✅ Dockerfile optimizado
- ✅ Health checks
- ✅ Documentación completa
- ✅ Cliente de testing
- ✅ Ejemplos de requests

---

## 📝 Notas Importantes

1. **Score de Compatibilidad**: El algoritmo es modular y puede ser ajustado modificando los pesos en `matching_engine.py`

2. **Distancia Geográfica**: Usa la fórmula Haversine para calcular distancia entre coordenadas (lat/lng)

3. **Expiration**: Los matches tienen una fecha de expiración de 7 días

4. **Índices**: Los índices en MongoDB están optimizados para queries frecuentes

5. **Error Handling**: Manejo completo de excepciones y logs detallados

---

## 🔄 Próximos Pasos Opcionales

1. Agregar eventos en RabbitMQ para notificaciones
2. Implementar caché en Redis para searches frecuentes
3. Agregar machine learning para mejorar recommendations
4. Implementar API de feedback para mejorar el algoritmo
5. Agregar métricas y telemetría

---

**Fecha de Creación**: Mayo 16, 2024
**Versión**: 1.0.0
**Status**: ✅ Implementado y Listo para Usar
