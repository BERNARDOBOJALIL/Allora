# Match Service

Servicio de matching e compatibilidad para la aplicación de citas Allora.

## Descripción

El Match Service es responsable de:

1. **Cálculo de compatibilidad** entre usuarios basado en:
   - Edad y preferencias de edad
   - Género y preferencias de género
   - Proximidad geográfica (distancia)
   - Intereses comunes
   - Ubicación

2. **Gestión de matches**:
   - Crear matches entre usuarios
   - Actualizar estado de matches (aceptado/rechazado)
   - Listar matches pendientes y completados
   - Encontrar potenciales matches recomendados

## Algoritmo de Compatibilidad

El sistema calcula un score de compatibilidad de 0-100 basado en:

- **Compatibilidad de edad (25 puntos)**: Verifica que ambos usuarios cumplan con las preferencias de edad
- **Compatibilidad de género (20 puntos)**: Verifica preferencias de género
- **Proximidad geográfica (25 puntos)**: Calcula distancia usando fórmula Haversine
- **Intereses comunes (30 puntos)**: Cantidad de intereses compartidos

Score mínimo requerido: 50 puntos (configurable)

## Endpoints

### Health Check
```
GET /health
```

### Encontrar Matches Potenciales
```
GET /users/{user_id}/matches?limit=10&skip=0
```

Retorna matches potenciales ordenados por score de compatibilidad.

### Calcular Compatibilidad
```
POST /compatibility
{
    "user_a_id": "userId1",
    "user_b_id": "userId2"
}
```

### Crear Match
```
POST /matches
{
    "user_a_id": "userId1",
    "user_b_id": "userId2"
}
```

### Obtener Match
```
GET /matches/{match_id}
```

### Obtener Todos los Matches de un Usuario
```
GET /users/{user_id}/all-matches?status=PENDING&limit=20&skip=0
```

Estados posibles: `PENDING`, `ACCEPTED`, `REJECTED`, `EXPIRED`

### Actualizar Estado de Match
```
PUT /matches/{match_id}
{
    "status": "ACCEPTED"
}
```

### Eliminar Match
```
DELETE /matches/{match_id}
```

## Estructura de Datos

### Documento Match
```json
{
    "_id": ObjectId,
    "user_a_id": "string",
    "user_b_id": "string",
    "status": "PENDING|ACCEPTED|REJECTED|EXPIRED",
    "compatibility_score": 0.0-100.0,
    "reasons": ["reason1", "reason2"],
    "created_at": "datetime",
    "updated_at": "datetime",
    "expires_at": "datetime",
    "metadata": {}
}
```

### Colecciones MongoDB
- `matches`: Almacena matches entre usuarios
- `user_profiles`: Perfiles de usuarios (caché local)

## Configuración

Variables de entorno (`.env`):

```env
MONGODB_URL=mongodb://root:password@mongodb:27017
MONGODB_DB=match_service
AUTH_SERVICE_URL=http://auth-service:8000
LOCATION_SERVICE_URL=http://location-service:8003
LOG_LEVEL=INFO
MAX_DISTANCE_KM=50.0
MIN_COMPATIBILITY_SCORE=0.5
```

## Integración con Otros Servicios

- **Auth Service**: Obtiene perfiles de usuario y validación
- **Location Service**: Obtiene ubicaciones actuales para cálculo de distancia
- **API Gateway**: Punto de entrada para todas las solicitudes

## Desarrollo Local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servicio
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

## Testing

Ejemplo de request para crear un match:

```bash
curl -X POST http://localhost:8002/matches \
  -H "Content-Type: application/json" \
  -d '{
    "user_a_id": "user1",
    "user_b_id": "user2"
  }'
```
