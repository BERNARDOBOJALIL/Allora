# Onboarding Conversacional con Allora Agent

Este documento describe cómo funciona la conversación con el agente de IA (Allora) durante el registro para construir y enriquecer el perfil del usuario. Está pensado para desarrolladores y agentes que deban integrar o mejorar el flujo de onboarding.

Resumen
- Momentos clave: registro -> llamada al agente -> persistencia de memorias -> continuación interactiva desde frontend.
- Endpoint del agente externo: `https://alloraagent.onrender.com/chat` (POST).
- Formato principal entre servicios: el backend realiza una llamada best-effort al agente y persiste `memory_updates` en MongoDB (`allora_auth.profiles`).

Objetivos del flujo
- Extraer datos relevantes de personalidad, intereses y preferencias mediante conversación guiada.
- Mantener un conjunto de memorias estructuradas que el frontend utiliza para mostrar un perfil enriquecido.
- Permitir que el usuario revise/edite el contenido generado por el agente y continúe la conversación si lo desea.

1) Punto de invocación (qué llama al agente)
- Actualmente: `auth-service` llama al agente justo después de crear el usuario en `POST /auth/register`.
- La llamada es "best-effort": si el agente no responde o hay error, el registro NO falla.

2) Payload que envía el backend al agente (ejemplo)
- Método: POST
- URL: `https://alloraagent.onrender.com/chat`
- Body JSON:
```json
{
  "user_id": "<user_id>",
  "thread_id": "onboarding-<user_id>",
  "message": "Initialize profile for new user. Nombre: <nombre>; Email: <email>; Telefono: <telefono>"
}
```

3) Respuesta esperada del agente (contracto)
- El agente debe devolver al menos:
  - `assistant_message`: texto que se le puede mostrar al usuario (sugerencia, pregunta, resumen)
  - `memory_updates`: objeto con upserts/deltas para las memorias (profile_memory, context_memory, preference_memory)
  - `conversation_state` (opcional): estado de progreso del onboarding (turn_count, should_continue...)

Ejemplo de respuesta:
```json
{
  "assistant_message": "¡Genial! ¿Qué te gusta hacer en tu tiempo libre?",
  "memory_updates": {
    "profile_memory": {"interests": ["música lo-fi"], "hobbies": ["producir beats"]},
    "context_memory": {"recent_topics": ["música"]},
    "preference_memory": {"conversation_style": "amigable"}
  },
  "conversation_state": {"turn_count": 1, "should_continue": true}
}
```

4) Persistencia en backend
- `auth-service` (implementación actual) toma `memory_updates` y las guarda en la colección `profiles` en la BD `allora_auth` usando documento con la forma:
```json
{
  "user_id": "<user_id>",
  "profile_memory": {...},
  "context_memory": {...},
  "preference_memory": {...},
  "updated_at": "<iso-timestamp>"
}
```
- Reglas de fusión sugeridas (server-side):
  - Para listas (intereses, hobbies): merge por concatenación + deduplicado.
  - Para escalares (social_style, vibe_summary): escribir si el valor no es nulo o es más completo.
  - Para claves complejas: usar semántica de delta (agregar/actualizar) provista por el agente si existiera.

5) Qué debe hacer el frontend tras el registro
- Consumir el backend como fuente de verdad y no llamar al agente directamente desde React.
- Mostrar el `assistant_message` devuelto por `POST /auth/register` en un modal/stepper de Onboarding.
- Si el usuario continúa la conversación, enviar el siguiente mensaje a `POST /auth/onboarding/{user_id}` con el mismo `thread_id` para mantener el contexto.
- Cargar el perfil enriquecido desde `GET /auth/profile-memory/{user_id}` cuando quieras pintar el estado acumulado.
- Permitir al usuario editar/confirmar campos generados automáticamente.
- Ofrecer un botón "Continuar conversación" que use el backend para reenviar el mensaje al agente y mostrar la respuesta.

6) Conversación interactiva (continuar onboarding)
- Interacción típica:
  1. Frontend envía la respuesta del usuario al backend: POST `/auth/onboarding/{user_id}` (endpoint recomendado) que a su vez reenvía al agente con `thread_id` consistente.
  2. Backend reenvía el mensaje del usuario al agente manteniendo `thread_id` y almacena cualquier `memory_updates` devuelto.
  3. Backend devuelve `assistant_message` y `memory_updates` al frontend.
- Ejemplo request interno al agent (máxima interoperabilidad):
```json
{
  "user_id": "<user_id>",
  "thread_id": "onboarding-<user_id>",
  "message": "Me gusta el senderismo y cocinar."
}
```
- Ejemplo response (como antes): `assistant_message` + `memory_updates`.

7) Consideraciones de seguridad y límites
- No invocar directamente el agente externo desde el cliente sin control (costos, rate-limits, fugas de datos).
- El backend debe validar y sanitizar mensajes si planea reenviarlos al agente.
- Manejar errores del agente: timeout, 5xx. Politica: retries exponenciales (1-2 intentos) y fallback a registro sin enriquecimiento.

8) Sugerencias de UX
- Mostrar claramente que el "Onboarding" es conversacional y que puede completarse más tarde.
- Permitir review y edición de elementos claves: `nombre`, `bio`, `intereses`, `hobbies`.
- Mostrar progreso (p. ej. 3/5 preguntas completadas).
- Guardar cambios locales en caso de fallo de red y reintentar.

9) Extensiones y mejoras técnicas (opcional)
- El backend ya puede devolver `assistant_message` y `onboarding_state` en `POST /auth/register` para mostrar el primer paso de onboarding sin esperar otra llamada.
- `auth-service` expone `POST /auth/onboarding/{user_id}` y `GET /auth/profile-memory/{user_id}` como contrato estable para React.
- Registrar métricas: latencia de agente, tasa de fallos, porcentaje de usuarios que completan onboarding.

10) Ejemplos de código (cliente simplificado)
- Node fetch (frontend) -> no recomendado para llamar al agente directamente:
```js
// Registrar (pasando por gateway)
await fetch('/auth/register', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ nombre, email, password }) });

// Obtener profile_memory (si backend expone endpoint)
const mem = await fetch(`/auth/profile-memory/${userId}`, { headers: { Authorization: `Bearer ${token}` }}).then(r=>r.json());
```
- Python (backend reenvío con httpx):
```py
import httpx
async with httpx.AsyncClient(timeout=10.0) as client:
    resp = await client.post('https://alloraagent.onrender.com/chat', json={'user_id': user_id, 'thread_id': thread_id, 'message': message})
    data = resp.json()
    # manejar data['memory_updates']
```

11) Resumen rápido para implementadores
- Llamar al agente desde backend con `thread_id` consistente para cada usuario.
- Persistir `memory_updates` en `allora_auth.profiles` y exponerlos con un endpoint protegido para que el frontend los consuma.
- Mostrar el `assistant_message` en el onboarding modal y permitir edición/continuación de la conversación.
- Tratar errores del agente con retries y fallback silencioso.

Si quieres, genero:
- un endpoint ejemplo `POST /auth/onboarding/{user_id}` y su implementación en `auth-service`, o
- fragmentos de UI (modal + llamadas JS) para incorporar el `assistant_message` y continuar la conversación.
