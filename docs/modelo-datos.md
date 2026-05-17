# Modelo de Datos

## Base de datos NoSQL - MongoDB

El backend usa MongoDB para persistir los dominios de autenticacion y chat. Las colecciones se separan por base de datos logica para mantener independencia entre microservicios:

- `allora_auth`: usuarios, memoria de perfil, tokens de sesion y codigos de verificacion.
- `allora_chat`: conversaciones y mensajes.

```mermaid
erDiagram
    USERS {
        ObjectId _id PK
        string nombre
        string email UK
        string telefono UK
        string password_hash
        string oauth_provider
        string oauth_provider_id
        string role
        string plan
        boolean is_active
        boolean is_email_verified
        boolean is_phone_verified
        boolean is_blocked
        datetime created_at
        datetime updated_at
        datetime last_login
        datetime password_changed_at
    }

    PROFILES {
        ObjectId _id PK
        string user_id FK
        object profile_memory
        object context_memory
        object preference_memory
        datetime updated_at
    }

    REFRESH_TOKENS {
        ObjectId _id PK
        string user_id FK
        string token_hash UK
        datetime expires_at
        datetime revoked_at
        datetime created_at
    }

    VERIFICATION_CODES {
        ObjectId _id PK
        string user_id FK
        string email
        string telefono
        string purpose
        string code_hash
        datetime expires_at
        datetime used_at
        datetime created_at
    }

    CONVERSATIONS {
        ObjectId _id PK
        string[] participant_ids FK
        string participant_key UK
        string match_id
        string last_message
        datetime last_message_at
        datetime created_at
        datetime updated_at
    }

    MESSAGES {
        ObjectId _id PK
        string conversation_id FK
        string sender_id FK
        string receiver_id FK
        string content
        string message_type
        string status
        datetime created_at
        datetime delivered_at
        datetime read_at
        datetime deleted_at
    }

    USERS ||--o| PROFILES : "tiene memoria"
    USERS ||--o{ REFRESH_TOKENS : "emite sesiones"
    USERS ||--o{ VERIFICATION_CODES : "recibe codigos"
    USERS }o--o{ CONVERSATIONS : "participa en"
    CONVERSATIONS ||--o{ MESSAGES : "contiene"
    USERS ||--o{ MESSAGES : "envia"
    USERS ||--o{ MESSAGES : "recibe"
```

### Colecciones por base de datos

| Base de datos | Coleccion | Microservicio propietario | Proposito |
|---|---|---|---|
| `allora_auth` | `users` | Auth Service | Identidad, credenciales, rol, plan y estado de cuenta. |
| `allora_auth` | `profiles` | Auth Service | Memoria de perfil, contexto y preferencias generadas durante onboarding. |
| `allora_auth` | `refresh_tokens` | Auth Service | Tokens de renovacion con hash, expiracion y revocacion. |
| `allora_auth` | `verification_codes` | Auth Service | Codigos de verificacion de email, telefono y recuperacion de password. |
| `allora_chat` | `conversations` | Chat Service | Conversaciones entre dos participantes, ultimo mensaje y relacion opcional con match. |
| `allora_chat` | `messages` | Chat Service | Mensajes persistidos, emisor, receptor, estado de entrega/lectura y borrado logico. |

### Indices principales

| Coleccion | Indice | Tipo |
|---|---|---|
| `users` | `email` | Unico parcial cuando `email` es string. |
| `users` | `telefono` | Unico parcial cuando `telefono` es string. |
| `users` | `oauth_provider`, `oauth_provider_id` | Unico parcial para cuentas OAuth. |
| `refresh_tokens` | `token_hash` | Unico. |
| `refresh_tokens` | `user_id`, `expires_at` | Consulta por usuario y limpieza por expiracion. |
| `verification_codes` | `code_hash` | Busqueda de codigo. |
| `verification_codes` | `purpose`, `email`, `telefono` | Verificacion por canal y proposito. |
| `conversations` | `participant_key` | Unico para evitar conversaciones duplicadas entre los mismos usuarios. |
| `conversations` | `participant_ids`, `match_id`, `updated_at` | Listado por usuario, asociacion con match y ordenamiento reciente. |
| `messages` | `conversation_id`, `created_at` | Paginacion cronologica de mensajes por conversacion. |
| `messages` | `receiver_id`, `status` | Busqueda de mensajes pendientes/leidos por receptor. |
| `messages` | `sender_id`, `created_at` | Historial por emisor. |
