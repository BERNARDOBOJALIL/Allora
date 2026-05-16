# Frontend Agent Guide — Mini Front para Allora (flujo de app de citas)

Propósito
- Proveer a un agente o desarrollador una guía clara para implementar un frontend mínimo pero útil para una app de citas: registro y onboarding conversacional vía Allora agent, exploración de perfiles, emparejamientos (matches), y mensajería.

Resumen del flujo de la app de citas
- Registro → Onboarding conversacional (Allora agent) → Perfil completado (automático/parcial) → Explorar perfiles → Interacción → Match → Chat → Notificaciones y presencia.




Endpoints clave (por el API Gateway)
- Public:
  - POST `/auth/register` — registro. Body: `{ nombre, email?, telefono?, password }`.
  - POST `/auth/login` — login. Body: `{ identifier, password }`.
- Protected (Bearer):
  - GET `/me` — detalles del usuario.
  - GET `/services/status` — estado de microservicios.
  - Chat:
    - POST `/chat/conversations` body `{ participant_id }` — crear conversación.
    - GET `/chat/conversations` — listar conversaciones.
    - GET `/chat/conversations/{conversation_id}/messages` — listar mensajes.
    - POST `/chat/conversations/{conversation_id}/messages` body `{ content }` — enviar mensaje.
  - Profile/profiles (recomendado): añadir endpoint para leer `profile_memory` generado por Allora: e.g. GET `/auth/profile-memory/{user_id}`.

Contratos de respuesta (lo que devuelve hoy)
- POST `/auth/register` (gateway -> auth-service)
  - Status: `201`
  - Devuelve `UserResponse` (NO devuelve `assistant_message` del agente):
  - Ejemplo:
```json
{
  "id": "6826f7b2e2f7c4f0f2a2c1a8",
  "nombre": "Demo User",
  "email": "demo@example.com",
  "telefono": null,
  "oauth_provider": null,
  "role": "user",
  "plan": "free",
  "is_active": true,
  "is_email_verified": false,
  "is_phone_verified": false,
  "is_blocked": false,
  "created_at": "2026-05-16T15:10:20.123456",
  "updated_at": "2026-05-16T15:10:20.123456",
  "last_login": null,
  "password_changed_at": null,
  "dev_codes": {
    "email": "123456"
  }
}
```

- POST `/auth/login`
  - Status: `200`
  - Devuelve `TokenResponse`:
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<refresh>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "6826f7b2e2f7c4f0f2a2c1a8",
    "nombre": "Demo User",
    "email": "demo@example.com",
    "role": "user",
    "plan": "free",
    "is_active": true,
    "is_email_verified": false,
    "is_phone_verified": false,
    "is_blocked": false,
    "created_at": "2026-05-16T15:10:20.123456",
    "updated_at": "2026-05-16T15:10:20.123456"
  }
}
```

- GET `/me`
  - Status: `200`
  - Devuelve desde gateway:
```json
{
  "user_id": "6826f7b2e2f7c4f0f2a2c1a8",
  "email": "demo@example.com",
  "token_payload": {
    "sub": "6826f7b2e2f7c4f0f2a2c1a8",
    "email": "demo@example.com",
    "role": "user",
    "plan": "free",
    "iss": "auth-service"
  }
}
```

- GET `/services/status`
  - Status: `200`
  - Devuelve:
```json
{
  "services": [
    {
      "name": "auth-service",
      "label": "Auth",
      "status": "ok",
      "message": "responde",
      "details": {"service": "auth-service", "status": "ok"}
    },
    {
      "name": "chat-service",
      "label": "Chat",
      "status": "degraded",
      "message": "...error..."
    }
  ]
}
```

- Chat
  - POST `/chat/conversations` -> `ConversationResponse`
```json
{
  "id": "6826f9e3e2f7c4f0f2a2c1bc",
  "participant_ids": ["user_a", "user_b"],
  "match_id": null,
  "last_message": null,
  "last_message_at": null,
  "created_at": "2026-05-16T15:12:03.100000",
  "updated_at": "2026-05-16T15:12:03.100000",
  "unread_count": 0
}
```
  - GET `/chat/conversations` -> `ConversationResponse[]`
  - GET `/chat/conversations/{conversation_id}/messages` -> `MessageResponse[]`
```json
[
  {
    "id": "6826fa15e2f7c4f0f2a2c1ce",
    "conversation_id": "6826f9e3e2f7c4f0f2a2c1bc",
    "sender_id": "user_a",
    "receiver_id": "user_b",
    "content": "Hola",
    "message_type": "text",
    "status": "sent",
    "created_at": "2026-05-16T15:12:53.100000",
    "delivered_at": null,
    "read_at": null,
    "deleted_at": null
  }
]
```
  - POST `/chat/conversations/{conversation_id}/messages` -> `MessageResponse`
  - POST `/chat/conversations/{conversation_id}/read` ->
```json
{
  "message": "Mensajes marcados como leidos",
  "updated_count": 3
}
```

- Nearby / ubicación
  - GET `/location/nearby?lat={lat}&lng={lng}&radius_km={km}`
  - Devuelve:
```json
{
  "count": 2,
  "nearby": [
    {
      "user_id": "user_b",
      "lat": 19.43,
      "lng": -99.13,
      "distance_km": 1.243,
      "room_id": null
    }
  ]
}
```

- Notifications (servicio actual)
  - Endpoint disponible hoy: `notification-service` expone `GET /notifications/{user_id}` y `PATCH /notifications/read`.
  - Nota: el gateway actual no tiene proxy `/notifications`, así que se consume directo (ej. `http://localhost:8004/notifications/{user_id}`) o se añade proxy en gateway.
  - Estructura de `NotificationResponse`:
```json
{
  "id": "1f4a7d6c-b3d1-4f0f-8fd5-b1d8aaac7f10",
  "user_id": "5df0f4b3-924a-4bc3-b61d-58fd7cbe58bd",
  "type": "message_sent",
  "title": "Nuevo mensaje",
  "body": "Ana: Hola, ¿cómo estás?",
  "extra_data": {
    "from_user_id": "...",
    "conversation_id": "..."
  },
  "read": false,
  "created_at": "2026-05-16T15:20:00"
}
```

Estructura de perfil (campos para frontend)
- Importante: hoy el perfil enriquecido por Allora NO regresa en `POST /auth/register`; se persiste en Mongo (`allora_auth.profiles`).
- Documento `profiles` esperado:
```json
{
  "user_id": "6826f7b2e2f7c4f0f2a2c1a8",
  "profile_memory": {
    "interests": ["lo-fi music"],
    "traits": ["curiosa"],
    "social_style": "selective",
    "vibe_summary": "tranquila y creativa",
    "favorite_environments": ["cafes", "parques"],
    "hobbies": ["fotografia"],
    "emotional_style": "calida"
  },
  "context_memory": {
    "recent_topics": ["viajes", "musica"],
    "evolving_interests": ["senderismo"],
    "life_updates": ["se mudó recientemente"],
    "recent_social_behavior": "mas abierta a conocer gente",
    "current_mood_theme": "optimista"
  },
  "preference_memory": {
    "conversation_style": "friendly",
    "prefers_short_questions": false,
    "depth_preference": "medium",
    "sensitive_topics": ["familia"]
  },
  "updated_at": "2026-05-16T15:10:21.100000"
}
```

Campos del perfil que debe usar el frontend (mapeo sugerido)
- Tarjeta pública de discover:
  - `display_name`: `nombre`
  - `bio_short`: `profile_memory.vibe_summary`
  - `interests`: `profile_memory.interests`
  - `social_style`: `profile_memory.social_style`
  - `distance_km`: viene de `/location/nearby`
- Perfil detallado:
  - `hobbies`: `profile_memory.hobbies`
  - `favorite_environments`: `profile_memory.favorite_environments`
  - `traits`: `profile_memory.traits`
  - `emotional_style`: `profile_memory.emotional_style`
  - `current_mood_theme`: `context_memory.current_mood_theme`
  - `depth_preference`: `preference_memory.depth_preference`

Onboarding conversacional (integración con Allora agent)
- Al registrar, `auth-service` ya llama a `https://alloraagent.onrender.com/chat` (best-effort) y guarda `memory_updates` en la colección `profiles` de la DB `allora_auth`.
- UX sugerida:
  1. Registrar usuario desde frontend.
  2. Tras registro (o primer login), abrir modal/stepper "Onboarding" que muestre el `assistant_message` y permita al usuario expandir o editar respuestas.
  3. Permitir "continuar conversación": enviar un nuevo mensaje al agente (desde backend o cliente) para seguir llenando perfil.

Data model y persistencia (resumen)
- `profiles` collection (DB `allora_auth`): campos esperados: `user_id`, `profile_memory`, `context_memory`, `preference_memory`, `updated_at`.
- `UserResponse` en `auth-service` devuelve el usuario. Si deseas incluir el `assistant_message` en la respuesta de registro, hay que extender `UserResponse`.

Location usage notes
- Para mostrar personas cerca del usuario:
  - Ideal: el frontend obtiene la ubicación del usuario (navigator.geolocation), luego llama a `GET /location/nearby?lat={lat}&lng={lng}&radius_km=5` a través del gateway (`/location/nearby`).
  - Alternativa en tiempo real: conectar vía WebSocket al endpoint `/ws/{user_id}` y enviar actualizaciones periódicas con `{ lat, lng, timestamp }`. El `location-service` broadcasting enviará actualizaciones a usuarios en la misma room.
  - Para UX de "personas cerca": al obtener la lista `nearby`, mostrar tarjetas similares a "explore" y permitir filtros por distancia, intereses o edad.



Ejemplo de flujo UI-API (paso a paso)
1. Usuario envía POST `/auth/register`.
2. Backend crea usuario y realiza POST al agente Allora en `https://alloraagent.onrender.com/chat`.
3. Backend persiste `memory_updates` en `profiles`.
4. Frontend, tras registro o primer login, llama a GET `/auth/profile-memory/{user_id}` (si exists) o hace una llamada cliente a Allora para mostrar `assistant_message`.
5. Usuario revisa/edita información y confirma perfil.
6. Perfil aparece en pool de exploración y puede recibir likes.
7. En caso de match mutuo, crear chat y permitir mensajería.

