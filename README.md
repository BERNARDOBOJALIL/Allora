# Allora - Arquitectura Backend

Allora esta estructurado como un backend de microservicios con una puerta de entrada principal, servicios especializados, persistencia por dominio, Redis para estados temporales/cache y RabbitMQ para comunicacion basada en eventos.

## Diagrama General

```mermaid
flowchart TB
    Client[Cliente Web / Mobile / Postman]

    subgraph Edge["Entrada al sistema"]
        Gateway["API Gateway\nFastAPI\n:8000"]
    end

    subgraph Backend["Servicios backend"]
        Auth["Auth Service\nUsuarios, login, JWT\n:8001"]
        Chat["Chat Service\nConversaciones y mensajes\n:8006"]
        Location["Location Service\nUbicacion y WebSockets\n:8003"]
        Notifications["Notification Service\nNotificaciones\n:8004"]
        Users["User Service\nPerfil / preferencias\n:8005\nplaceholder actual"]
        Match["Match Service\nMatches\n:8002\nplaceholder actual"]
    end

    subgraph Data["Persistencia y estado"]
        MongoAuth[("MongoDB\nallora_auth")]
        MongoChat[("MongoDB\nallora_chat")]
        NotificationDB[("DB Notificaciones\nSQLAlchemy/Postgres esperado")]
        Redis[("Redis\npresencia, unread counters,\ncache y estados temporales")]
    end

    subgraph Messaging["Mensajeria"]
        Rabbit["RabbitMQ\nTopic exchanges / queues"]
    end

    Client -->|REST / HTTP| Gateway
    Client -->|WebSocket ubicacion| Location

    Gateway -->|/auth/* publico| Auth
    Gateway -->|JWT + X-User-Id| Chat
    Gateway -->|JWT + X-User-Id| Location
    Gateway -->|JWT + X-User-Id| Users
    Gateway -->|JWT + X-User-Id| Match

    Auth -->|users, refresh_tokens,\nverification_codes| MongoAuth
    Chat -->|conversations, messages| MongoChat
    Chat -->|presencia, no leidos,\ncache conversacion| Redis
    Gateway -->|JWKS / validacion token| Auth

    Chat -->|publica eventos:\nconversation.created\nmessage.sent\nmessages.read\nuser.online\nuser.offline| Rabbit
    Match -->|publica evento:\nmatch.created| Rabbit
    Auth -->|publica evento esperado:\nuser.registered| Rabbit
    Rabbit -->|consume eventos relevantes| Notifications
    Notifications -->|guarda notificaciones| NotificationDB
```

## Flujo Completo de la Aplicacion

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant G as API Gateway
    participant A as Auth Service
    participant C as Chat Service
    participant L as Location Service
    participant M as Match Service
    participant R as Redis
    participant MQ as RabbitMQ
    participant N as Notification Service
    participant DB as Bases de datos

    U->>G: POST /auth/register o /auth/login
    G->>A: Reenvia solicitud publica
    A->>DB: Persiste usuario / tokens / codigos
    A-->>G: JWT + refresh token + datos de usuario
    G-->>U: Respuesta autenticada

    U->>G: Solicitud protegida con Bearer JWT
    G->>A: Consulta JWKS / valida token
    A-->>G: Clave publica / token valido
    G->>C: Reenvia request con X-User-Id

    U->>G: POST /chat/conversations
    G->>C: Crear conversacion
    C->>DB: Guarda conversacion en MongoDB
    C->>R: Cachea datos de conversacion
    C->>MQ: Publica conversation.created
    C-->>G: Conversacion creada
    G-->>U: Respuesta

    U->>G: POST /chat/conversations/{id}/messages
    G->>C: Enviar mensaje
    C->>DB: Guarda mensaje y actualiza conversacion
    C->>R: Incrementa unread counter del receptor
    C->>MQ: Publica message.sent
    MQ->>N: Entrega evento message.sent
    N->>DB: Crea notificacion para receptor
    C-->>G: Mensaje creado
    G-->>U: Respuesta

    U->>G: POST /chat/presence/online
    G->>C: Marca usuario online
    C->>R: Guarda estado temporal con TTL
    C->>MQ: Publica user.online

    U->>L: WebSocket /ws/{user_id}
    L->>L: Valida token y administra sala/ubicacion
    L-->>U: Broadcast de ubicaciones en tiempo real

    U->>G: Accion de match
    G->>M: Reenvia solicitud a Match Service
    M->>DB: Persiste match
    M->>MQ: Publica match.created
    MQ->>N: Entrega match.created
    N->>DB: Crea notificaciones de match
```

