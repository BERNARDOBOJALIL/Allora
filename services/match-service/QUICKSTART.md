# Match Service - Guía Rápida

## 🚀 Inicio Rápido

### Opción 1: Con Docker Compose (Recomendado)

```bash
cd Allora
docker-compose up --build match-service
```

El servicio estará disponible en: **http://localhost:8002**

### Opción 2: Desarrollo Local

```bash
cd services/match-service

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

---

## 🧪 Pruebas Rápidas

### 1. Health Check

```bash
curl http://localhost:8002/health
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "service": "match-service"
}
```

### 2. Calcular Compatibilidad Entre Dos Usuarios

```bash
curl -X POST http://localhost:8002/compatibility \
  -H "Content-Type: application/json" \
  -d '{
    "user_a_id": "507f1f77bcf86cd799439011",
    "user_b_id": "507f1f77bcf86cd799439012"
  }'
```

**Respuesta:**
```json
{
  "user_a_id": "507f1f77bcf86cd799439011",
  "user_b_id_id": "507f1f77bcf86cd799439012",
  "score": 75.5,
  "reasons": [
    "Age preferences match",
    "Gender preferences compatible",
    "Close proximity (15.2 km)",
    "Shared interests: travel, music"
  ]
}
```

### 3. Crear un Match

```bash
curl -X POST http://localhost:8002/matches \
  -H "Content-Type: application/json" \
  -d '{
    "user_a_id": "507f1f77bcf86cd799439011",
    "user_b_id": "507f1f77bcf86cd799439012"
  }'
```

### 4. Ver Matches Potenciales para un Usuario

```bash
curl http://localhost:8002/users/507f1f77bcf86cd799439011/matches?limit=5
```

### 5. Ver Todos los Matches de un Usuario

```bash
curl http://localhost:8002/users/507f1f77bcf86cd799439011/all-matches?status=PENDING
```

### 6. Actualizar Status de un Match

```bash
curl -X PUT http://localhost:8002/matches/{match_id} \
  -H "Content-Type: application/json" \
  -d '{"status": "ACCEPTED"}'
```

---

## 📊 Ejemplo de Algoritmo de Compatibilidad

### Datos de Entrada:

**Usuario A:**
- Edad: 28 años
- Género: Masculino
- Ubicación: Lat 40.7128, Lng -74.0060
- Intereses: viajes, música, cine
- Preferencias:
  - Edad: 23-35
  - Género: Femenino
  - Distancia máxima: 50 km

**Usuario B:**
- Edad: 26 años
- Género: Femenino
- Ubicación: Lat 40.7282, Lng -73.7949
- Intereses: viajes, fotografía, música
- Preferencias:
  - Edad: 25-32
  - Género: Masculino
  - Distancia máxima: 40 km

### Cálculo:

```
1. Edad: ✓ 28 está en 23-35 Y 26 está en 25-32 → +25 puntos
2. Género: ✓ M/F match → +20 puntos
3. Distancia: ✓ 12.5 km < 50km Y 12.5 km < 40km → +22 puntos
4. Intereses: ✓ 2 comunes (viajes, música) → +10 puntos

SCORE TOTAL: 77 / 100 ✓ MATCH VÁLIDO (>50)
```

---

## 📂 Estructura del Proyecto

```
match-service/
├── app/
│   ├── __init__.py              # Inicialización
│   ├── main.py                  # FastAPI app
│   ├── config.py                # Configuración
│   ├── models.py                # Modelos de datos
│   ├── schemas.py               # Esquemas Pydantic
│   ├── database.py              # Conexión MongoDB
│   └── matching_engine.py       # Lógica de matching
├── Dockerfile                   # Contenerización
├── requirements.txt             # Dependencias
├── README.md                    # Documentación
├── ARCHITECTURE.md              # Arquitectura
├── .env.example                 # Variables de ejemplo
├── test_client.py              # Cliente Python
└── examples.sh                 # Ejemplos cURL
```

---

## ⚙️ Configuración

### Variables de Entorno

```env
MONGODB_URL=mongodb://root:password@mongodb:27017
MONGODB_DB=match_service
AUTH_SERVICE_URL=http://auth-service:8000
LOCATION_SERVICE_URL=http://location-service:8003
LOG_LEVEL=INFO
MAX_DISTANCE_KM=50.0
MIN_COMPATIBILITY_SCORE=0.5
```

### Ajustar Sensibilidad del Matching

En `app/matching_engine.py`, línea del cálculo de score:

```python
# Aumentar peso de intereses comunes
interest_score = min(50, len(common_interests) * 10)  # En lugar de * 5

# O cambiar score mínimo requerido
self.min_score = 60.0  # En lugar de 50.0
```

---

## 🔍 Debugging

### Ver Logs

```bash
docker logs -f match-service
```

### Testear con Python

```bash
python test_client.py
```

### Testear con cURL

```bash
bash examples.sh
```

---

## 📋 API Reference Completa

### Endpoints Disponibles

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/compatibility` | Calcular compatibilidad |
| POST | `/matches` | Crear match |
| GET | `/matches/{id}` | Obtener match |
| PUT | `/matches/{id}` | Actualizar status |
| DELETE | `/matches/{id}` | Eliminar match |
| GET | `/users/{id}/matches` | Matches potenciales |
| GET | `/users/{id}/all-matches` | Todos los matches |

### Códigos de Estado HTTP

| Código | Significado |
|--------|------------|
| 200 | OK |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 404 | Not Found |
| 409 | Conflict |
| 500 | Internal Server Error |

---

## 🐛 Problemas Comunes

### "Match not found"
- Verificar que el match_id sea válido
- Verificar que el match no haya sido eliminado

### "One or both users not found"
- Verificar que Auth Service esté activo
- Verificar que los user_ids sean válidos

### "Distance too far"
- Aumentar `MAX_DISTANCE_KM` en variables de entorno
- O verificar que Location Service devuelva ubicaciones válidas

### "Compatibility score too low"
- Bajar `MIN_COMPATIBILITY_SCORE` en variables de entorno
- O ajustar las preferencias del usuario

---

## 📚 Documentación Completa

- **README.md** - Descripción general y detalles técnicos
- **ARCHITECTURE.md** - Diagramas y flujos de datos
- **API Endpoints** - Disponible en http://localhost:8002/docs (Swagger UI)

---

## 🤝 Contribuir

Para agregar nuevas funcionalidades:

1. Editar `matching_engine.py` para lógica
2. Agregar esquemas en `schemas.py`
3. Agregar endpoints en `main.py`
4. Actualizar documentación
5. Testear con `test_client.py`

---

## ✅ Checklist de Verificación

- [ ] Health check responde correctamente
- [ ] Puede crear matches entre usuarios válidos
- [ ] Calcula compatibilidad correctamente
- [ ] Rechaza matches con score bajo
- [ ] MongoDB guarda matches correctamente
- [ ] Los índices están optimizados
- [ ] Las ubicaciones se obtienen de Location Service
- [ ] Los perfiles se obtienen de Auth Service

---

**Versión**: 1.0.0
**Última Actualización**: Mayo 16, 2024
**Status**: ✅ Listo para Producción
