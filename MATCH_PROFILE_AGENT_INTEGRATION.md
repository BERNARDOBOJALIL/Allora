# Integracion Match Service + Profile Agent

## Objetivo

Conectar el `match-service` con el `profile-agent` para que el sistema de matches use la informacion suave del perfil del usuario: `interests`, `hobbies`, `personality_traits`, `favorite_environments`, `social_style`, `vibe_summary`, `dislikes` y `emotional_style`.

Actualmente el perfil construido por Allora se guarda en el servicio desplegado:

```text
https://alloraagent.onrender.com/profile/{user_id}
```

El `match-service` calcula compatibilidad usando datos del auth-service local, por lo que no ve la informacion que el usuario construye hablando con el agente o editando manualmente su perfil.

## Cambio Recomendado

El `match-service` debe consultar el `profile-agent` cuando calcula compatibilidad entre dos usuarios.

Agregar esta variable de entorno al backend del match-service:

```env
PROFILE_AGENT_URL=https://alloraagent.onrender.com
```

Si el proyecto usa `pydantic-settings`, agregarla tambien a la configuracion:

```python
PROFILE_AGENT_URL: str = "https://alloraagent.onrender.com"
```

## Endpoint Del Profile Agent

Para obtener el perfil construido:

```http
GET {PROFILE_AGENT_URL}/profile/{user_id}
```

Respuesta esperada:

```json
{
  "user_id": "user_abc123",
  "profile_memory": {
    "interests": ["cine", "cafe"],
    "personality_traits": ["tranquilo", "curioso"],
    "social_style": "Prefiere planes tranquilos.",
    "vibe_summary": "Persona creativa y calmada.",
    "favorite_environments": ["cafes", "parques"],
    "hobbies": ["fotografia", "senderismo"],
    "dislikes": ["ruido excesivo"],
    "emotional_style": "Expresa afecto con calma."
  },
  "profile_completion": 0.5
}
```

