# Frontend Guide — Grupos por proximidad y chat compartido

Este documento explica cómo debe implementar el frontend React el flujo de "grupos" de Allora. En este sistema, un grupo es un espacio creado por un usuario que se ubica en un punto geográfico, admite usuarios cercanos y habilita un chat compartido para quienes entran al espacio.

## Objetivo del flujo

- Un usuario crea un grupo desde el front.
- El grupo tiene nombre, descripción y foto.
- El grupo aparece en un mapa o listado de espacios cercanos.
- Los usuarios cercanos pueden unirse.
- Al unirse, obtienen acceso a un chat compartido del grupo.
- El grupo desaparece si nadie más se une en 1 hora o si sólo queda 1 persona después de haber tenido más miembros.

## Principios de implementación en el frontend

- El frontend debe ser la capa de experiencia de usuario.
- La lógica de negocio vive en backend.
- El frontend no debe crear el chat por su cuenta: sólo llama a los endpoints del backend.
- La fuente de verdad del estado del grupo es el backend.
- El frontend sólo pinta, envía acciones y sincroniza estado.

## Arquitectura recomendada

### Opción preferida
El frontend habla con el API Gateway:
- `http://localhost:8000/location/...`
- `http://localhost:8000/chat/...`
- `http://localhost:8000/auth/...`

### Alternativa local
Si pruebas sin gateway, puedes apuntar directo a:
- `http://localhost:8003/api/v1/...` para `location-service`
- `http://localhost:8006/...` para `chat-service`

## Concepto funcional

Un grupo tiene dos capas:

- `space` o espacio de proximidad: se crea en `location-service`.
- `group conversation`: se crea en `chat-service` y guarda el historial del grupo.

Cuando el creador crea el espacio, el backend crea automáticamente la conversación de grupo. Cuando otro usuario entra al espacio, también entra al chat de ese grupo.

## Flujo completo en el frontend

### 1. Obtener ubicación del usuario
Antes de listar grupos o intentar unirse, el frontend debe conocer la ubicación del usuario.

Ejemplo:
```js
navigator.geolocation.getCurrentPosition(
  (position) => {
    const lat = position.coords.latitude;
    const lng = position.coords.longitude;
  },
  (error) => {
    console.error('No se pudo obtener ubicación', error);
  },
);
```

### 2. Mostrar grupos cercanos
El front consulta los espacios cercanos con lat/lng.

Endpoint:
- `GET /location/spaces/nearby?lat={lat}&lng={lng}&radius_km={radius}`

Ejemplo de respuesta:
```json
{
  "count": 2,
  "spaces": [
    {
      "space_id": "space-c6fbe1b683f2",
      "name": "Parque Central Beats",
      "description": "Grupo para gente cerca del parque",
      "photo_base64": "ZmFrZS1pbWFnZS1iYXNlNjQ=",
      "owner_user_id": "user-a",
      "lat": 19.4326,
      "lng": -99.1332,
      "radius_km": 2,
      "members": ["user-a", "user-b"],
      "chat_conversation_id": "6a09283af8fae3c25f70fefa",
      "created_at": "2026-05-17T02:30:18.753106+00:00",
      "expires_at": "2026-05-17T03:30:18.753106+00:00",
      "distance_km": 0.243
    }
  ]
}
```

### 3. Crear un grupo
El usuario llena un formulario con:
- nombre
- descripción
- foto en base64
- ubicación
- radio máximo del grupo

Endpoint:
- `POST /location/spaces`

Body:
```json
{
  "user_id": "user123",
  "name": "Cafetería Centro",
  "description": "Grupo para quienes estén cerca del café",
  "photo_base64": "data:image/png;base64,...",
  "lat": 19.4326,
  "lng": -99.1332,
  "radius_km": 1.5
}
```

Respuesta:
```json
{
  "space_id": "space-c6fbe1b683f2",
  "name": "Cafetería Centro",
  "description": "Grupo para quienes estén cerca del café",
  "photo_base64": "data:image/png;base64,...",
  "owner_user_id": "user123",
  "lat": 19.4326,
  "lng": -99.1332,
  "radius_km": 1.5,
  "members": ["user123"],
  "chat_conversation_id": "6a09283af8fae3c25f70fefa",
  "created_at": "2026-05-17T02:30:18.753106+00:00",
  "expires_at": "2026-05-17T03:30:18.753106+00:00"
}
```

### 4. Unirse a un grupo
El usuario puede unirse si está dentro del radio del grupo.

Endpoint:
- `POST /location/spaces/{space_id}/join`

Body recomendado:
```json
{
  "user_id": "user456",
  "lat": 19.433,
  "lng": -99.133
}
```

Regla:
- Si el backend ya tiene la ubicación del usuario vía WebSocket, el front puede omitir `lat/lng`.
- Si no hay ubicación guardada, el front debe enviar `lat/lng` como fallback.

Respuesta:
```json
{
  "space_id": "space-c6fbe1b683f2",
  "name": "Cafetería Centro",
  "description": "Grupo para quienes estén cerca del café",
  "photo_base64": "data:image/png;base64,...",
  "owner_user_id": "user123",
  "lat": 19.4326,
  "lng": -99.1332,
  "radius_km": 1.5,
  "members": ["user123", "user456"],
  "chat_conversation_id": "6a09283af8fae3c25f70fefa",
  "created_at": "2026-05-17T02:30:18.753106+00:00",
  "expires_at": "2026-05-17T03:30:18.753106+00:00"
}
```

### 5. Salir del grupo
Endpoint:
- `POST /location/spaces/{space_id}/leave`

Body:
```json
{
  "user_id": "user456"
}
```

Si el grupo queda con 1 sola persona después de haber tenido más miembros, el backend lo elimina.

### 6. Abrir el chat del grupo
El chat compartido pertenece al grupo. El frontend debe usar el `chat_conversation_id` devuelto por `location-service`.

Endpoints de chat:
- `GET /chat/group-conversations`
- `GET /chat/group-conversations/{conversation_id}/messages`
- `POST /chat/group-conversations/{conversation_id}/messages`

Ejemplo para listar mensajes:
```js
const res = await fetch(`/chat/group-conversations/${conversationId}/messages`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-User-Id': userId,
  },
});
const messages = await res.json();
```

Ejemplo para enviar mensaje:
```js
await fetch(`/chat/group-conversations/${conversationId}/messages`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-User-Id': userId,
  },
  body: JSON.stringify({ content: message }),
});
```

## Contrato del frontend con el backend

### Headers
Para rutas protegidas el frontend debe enviar:
- `Authorization: Bearer <access_token>`
- `X-User-Id: <user_id>` cuando el endpoint de chat lo requiera

### Base64 de imágenes
La foto del grupo se guarda como base64. El frontend puede usar un `input type="file"`, leer el archivo como Data URL y enviar la cadena completa.

Ejemplo:
```js
const file = input.files[0];
const reader = new FileReader();
reader.onload = () => {
  const base64 = reader.result;
  // enviar base64 al backend
};
reader.readAsDataURL(file);
```

## Estado recomendado en React

### Estado de grupo
El frontend debería manejar algo así:
```ts
type Space = {
  space_id: string;
  name: string;
  description: string;
  photo_base64: string;
  owner_user_id: string;
  lat: number;
  lng: number;
  radius_km: number;
  members: string[];
  chat_conversation_id?: string | null;
  created_at: string;
  expires_at?: string | null;
  distance_km?: number;
};
```

### Estado sugerido en la UI
- `nearbySpaces`
- `selectedSpace`
- `currentSpace`
- `currentConversationId`
- `isCreatingSpace`
- `isJoiningSpace`
- `locationPermissionState`
- `geoPosition`


## Ejemplo de flujo real en React

```ts
1. Obtener userId y token después de login.
2. Pedir ubicación al navegador.
3. Llamar a /location/spaces/nearby.
4. Mostrar tarjetas de espacios.
5. Si el usuario crea uno, llamar a /location/spaces.
6. Si el usuario se une, llamar a /location/spaces/{space_id}/join.
7. Guardar chat_conversation_id.
8. Abrir chat del grupo con /chat/group-conversations/{conversation_id}/messages.
9. Enviar mensajes por /chat/group-conversations/{conversation_id}/messages.


