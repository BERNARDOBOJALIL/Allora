## Flujo Principal de la Aplicación

Para acceder a las funcionalidades de Allora, tenemos un API Gateway que funciona como punto de entrada único para clientes web, móviles o herramientas como Postman.


# 1. Registro de Usuario

El usuario crea una cuenta dentro de la plataforma mediante el `Auth Service`.

## Endpoint

```http
POST /auth/register
```

## Request

```json
{
  "nombre": "Demo User",
  "email": "demo@example.com",
  "telefono": null,
  "password": "Password123!"
}
```

## Response exitosa

```json
{
  "id": "664f...",
  "nombre": "Demo User",
  "email": "demo@example.com",
  "telefono": null,
  "role": "USER",
  "plan": "FREE",
  "is_active": true,
  "is_email_verified": false,
  "is_phone_verified": false,
  "is_blocked": false,
  "created_at": "2026-05-17T12:00:00Z",
  "updated_at": "2026-05-17T12:00:00Z"
}
```

## Evento publicado

```txt
user.registered
```

## curl

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Demo User","email":"demo@example.com","telefono":null,"password":"Password123!"}'
```

---

# 2. Inicio de Sesión

El usuario inicia sesión y recibe los tokens necesarios para acceder a las rutas protegidas.

## Endpoint

```http
POST /auth/login
```

**Autenticación:** No requerida.

## Request

```json
{
  "identifier": "demo@example.com",
  "password": "Password123!"
}
```

## Response exitosa

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<refresh_token>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "664f...",
    "nombre": "Demo User",
    "email": "demo@example.com",
    "role": "USER",
    "plan": "FREE"
  }
}
```

## curl

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"demo@example.com","password":"Password123!"}'
```

---

# 3. Usuario Autenticado

Permite validar el token JWT y obtener la información del usuario autenticado.

## Endpoint

```http
GET /me
```

**Autenticación:** Requerida.

## Headers

```txt
Authorization: Bearer <access_token>
```

## Response exitosa

```json
{
  "user_id": "664f...",
  "email": "demo@example.com",
  "token_payload": {
    "sub": "664f...",
    "email": "demo@example.com",
    "role": "USER",
    "plan": "FREE",
    "iss": "auth-service"
  }
}
```

## curl

```bash
curl http://localhost:8000/me \
  -H "Authorization: Bearer <access_token>"
```

---

# 4. Creación de Match

Cuando un usuario muestra interés por otro, el `Match Service` puede generar un match.

## Endpoint

```http
POST /matches
```

**Autenticación:** Requerida.

## Request

```json
{
  "target_user_id": "6650...",
  "action": "like"
}
```

## Response esperada

```json
{
  "match_id": "match_123",
  "user_a": "664f...",
  "user_b": "6650...",
  "status": "created",
  "created_at": "2026-05-17T12:00:00Z"
}
```

## Evento publicado

```txt
match.created
```

## curl

```bash
curl -X POST http://localhost:8000/matches \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"target_user_id":"6650...","action":"like"}'
```

---

# 5. Creación de Conversación

Después del match, el `Chat Service` crea una conversación privada.

## Endpoint

```http
POST /chat/conversations
```

**Autenticación:** Requerida.

## Request

```json
{
  "participant_id": "6650...",
  "match_id": "match_123"
}
```

## Response exitosa

```json
{
  "id": "6651...",
  "participant_ids": ["664f...", "6650..."],
  "match_id": "match_123",
  "last_message": null,
  "last_message_at": null,
  "created_at": "2026-05-17T12:00:00Z",
  "updated_at": "2026-05-17T12:00:00Z",
  "unread_count": 0
}
```

## Evento publicado

```txt
conversation.created
```

## curl

```bash
curl -X POST http://localhost:8000/chat/conversations \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"participant_id":"6650...","match_id":"match_123"}'
```

---

# 6. Enviar Mensaje

Permite enviar mensajes dentro de una conversación.

## Endpoint

```http
POST /chat/conversations/{conversation_id}/messages
```

**Autenticación:** Requerida.

## Request

```json
{
  "content": "Hola, ¿cómo estás?",
  "message_type": "TEXT"
}
```

## Response exitosa

```json
{
  "id": "6652...",
  "conversation_id": "6651...",
  "sender_id": "664f...",
  "receiver_id": "6650...",
  "content": "Hola, ¿cómo estás?",
  "message_type": "TEXT",
  "status": "SENT",
  "created_at": "2026-05-17T12:10:00Z",
  "delivered_at": null,
  "read_at": null,
  "deleted_at": null
}
```

## Evento publicado

```txt
message.sent
```

## curl

```bash
curl -X POST http://localhost:8000/chat/conversations/6651.../messages \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"content":"Hola, ¿cómo estás?","message_type":"TEXT"}'
```

---

# 7. Marcar Mensajes como Leídos

Marca mensajes como leídos dentro de una conversación.

## Endpoint

```http
POST /chat/conversations/{conversation_id}/read
```

**Autenticación:** Requerida.

## Response exitosa

```json
{
  "message": "Mensajes marcados como leidos",
  "updated_count": 3
}
```

## Evento publicado

```txt
messages.read
```

## curl

```bash
curl -X POST http://localhost:8000/chat/conversations/6651.../read \
  -H "Authorization: Bearer <access_token>"
```

---

# 8. Presencia de Usuario

Permite conocer si un usuario está conectado o desconectado.

## Usuario Online

### Endpoint

```http
POST /chat/presence/online
```

### Response

```json
{
  "user_id": "664f...",
  "is_online": true
}
```

### Evento publicado

```txt
user.online
```

### curl

```bash
curl -X POST http://localhost:8000/chat/presence/online \
  -H "Authorization: Bearer <access_token>"
```

---

## Usuario Offline

### Endpoint

```http
POST /chat/presence/offline
```

### Response

```json
{
  "user_id": "664f...",
  "is_online": false
}
```

### Evento publicado

```txt
user.offline
```

### curl

```bash
curl -X POST http://localhost:8000/chat/presence/offline \
  -H "Authorization: Bearer <access_token>"
```

---

# 9. Usuarios Cercanos

El `Location Service` permite buscar usuarios cercanos.

## Endpoint

```http
GET /location/api/v1/nearby
```

**Autenticación:** Requerida.

## Query Params

| Parámetro | Tipo | Descripción |
|---|---|---|
| `lat` | number | Latitud |
| `lng` | number | Longitud |
| `radius_km` | number | Radio de búsqueda |

## Ejemplo

```http
GET /location/api/v1/nearby?lat=19.4326&lng=-99.1332&radius_km=5
```

## Response exitosa

```json
{
  "count": 1,
  "nearby": [
    {
      "user_id": "6650...",
      "lat": 19.4327,
      "lng": -99.1331,
      "distance_km": 0.25,
      "room_id": "room_123"
    }
  ]
}
```

## curl

```bash
curl "http://localhost:8000/location/api/v1/nearby?lat=19.4326&lng=-99.1332&radius_km=5" \
  -H "Authorization: Bearer <access_token>"
```

---

# 10. Notificaciones

El `Notification Service` genera notificaciones persistentes relacionadas con mensajes, matches e interacciones.

## Endpoint

```http
GET /notifications/{user_id}
```

## Response exitosa

```json
[
  {
    "id": "notification_id",
    "user_id": "664f...",
    "type": "message_sent",
    "title": "Nuevo mensaje",
    "body": "Alguien: Hola",
    "read": false,
    "extra_data": {
      "conversation_id": "6651..."
    },
    "created_at": "2026-05-17T12:00:00Z"
  }
]
```

## curl

```bash
curl "http://localhost:8000/notifications/664f...?limit=20&offset=0" \
  -H "Authorization: Bearer <access_token>"
```

---
