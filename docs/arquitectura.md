

---

## 1. Diagrama de arquitectura general

```mermaid
flowchart LR
    Client["Cliente Web / Mobile / Postman"]

    subgraph Edge["Capa de entrada"]
        Gateway["API Gateway<br/>FastAPI<br/>Puerto 8000"]
    end

    subgraph Domain["Microservicios de dominio"]
        Auth["Auth Service<br/>Registro, login, JWT, JWKS<br/>Puerto 8001"]
        Users["User Service<br/>Perfil y preferencias<br/>Puerto 8005"]
        Match["Match Service<br/>Matches y compatibilidad<br/>Puerto 8002"]
        Chat["Chat Service<br/>Conversaciones, mensajes, presencia<br/>Puerto 8006"]
        Location["Location Service<br/>Check-in, salas, ubicacion, WebSocket<br/>Puerto 8003"]
        Notifications["Notification Service<br/>Notificaciones persistentes<br/>Puerto 8004"]
    end

    subgraph Data["Persistencia y estado"]
        MongoAuth[("MongoDB<br/>allora_auth")]
        MongoChat[("MongoDB<br/>allora_chat")]
        PostgresNotif[("PostgreSQL<br/>notificaciones")]
        Redis[("Redis<br/>presencia, unread counters, cache")]
    end

    subgraph Events["Mensajeria asincrona"]
        Rabbit["RabbitMQ<br/>Topic exchanges y queues durables"]
        ChatExchange["Exchange: allora.chat.events"]
        GeneralExchange["Exchange: allora.events"]
        NotificationQueue["Queue: notifications.queue"]
    end

    Client -->|"REST / HTTP"| Gateway
    Client -->|"WebSocket /ws/{user_id}"| Location

    Gateway -->|"GET JWKS / validacion JWT"| Auth
    Gateway -->|"/auth/register, /auth/login, /auth/refresh"| Auth
    Gateway -->|"Rutas protegidas + X-User-Id"| Users
    Gateway -->|"Rutas protegidas + X-User-Id"| Match
    Gateway -->|"Rutas protegidas + X-User-Id"| Chat
    Gateway -->|"Rutas protegidas + X-User-Id"| Location
    Gateway -->|"Rutas protegidas + X-User-Id"| Notifications

    Auth --> MongoAuth
    Chat --> MongoChat
    Chat --> Redis
    Location -->|"estado en memoria<br/>conexiones, salas, ubicaciones"| Location
    Notifications --> PostgresNotif

    Chat -->|"conversation.created<br/>message.sent<br/>messages.read<br/>user.online<br/>user.offline"| ChatExchange
    Match -->|"match.created"| GeneralExchange
    Auth -->|"user.registered"| GeneralExchange
    ChatExchange --> Rabbit
    GeneralExchange --> Rabbit
    Rabbit --> NotificationQueue
    NotificationQueue --> Notifications
```

---

## 2. Diagramas de secuencia

### 2.1 Registro, login y emision de tokens

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant G as API Gateway
    participant A as Auth Service
    participant M as MongoDB allora_auth

    U->>G: POST /auth/register
    G->>A: Reenvia solicitud publica
    A->>M: Verifica email/telefono y crea usuario
    A->>M: Guarda refresh token y codigos de verificacion
    A-->>G: Usuario registrado
    G-->>U: 201 Created

    U->>G: POST /auth/login
    G->>A: Reenvia credenciales
    A->>M: Busca usuario y valida password hash
    A->>M: Persiste refresh token
    A-->>G: Access token JWT + refresh token
    G-->>U: Sesion iniciada
```

### 2.2 Solicitud protegida mediante gateway

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario autenticado
    participant G as API Gateway
    participant A as Auth Service
    participant S as Servicio de dominio

    U->>G: Request protegida con Authorization: Bearer JWT
    alt Llave publica no esta cacheada o firma invalida
        G->>A: GET /auth/.well-known/jwks.json
        A-->>G: JWKS con llave publica RSA
    end
    G->>G: Valida firma, issuer y subject del JWT
    G->>S: Reenvia request + X-User-Id
    S-->>G: Respuesta del dominio
    G-->>U: Respuesta normalizada del gateway
```

### 2.3 Creacion de conversacion y envio de mensaje

```mermaid
sequenceDiagram
    autonumber
    actor U1 as Usuario A
    participant G as API Gateway
    participant C as Chat Service
    participant M as MongoDB allora_chat
    participant R as Redis
    participant MQ as RabbitMQ
    participant N as Notification Service
    participant P as PostgreSQL

    U1->>G: POST /chat/conversations
    G->>G: Valida JWT
    G->>C: Crear conversacion con X-User-Id
    C->>M: Busca conversacion por participant_key
    alt No existe conversacion
        C->>M: Inserta conversacion
        C->>R: Cachea metadata de conversacion
        C->>MQ: Publica conversation.created
    end
    C-->>G: Conversacion creada o existente
    G-->>U1: ConversationResponse

    U1->>G: POST /chat/conversations/{id}/messages
    G->>G: Valida JWT
    G->>C: Enviar mensaje con X-User-Id
    C->>M: Valida participacion y persiste mensaje
    C->>M: Actualiza last_message en conversacion
    C->>R: Incrementa unread counter del receptor
    C->>R: Actualiza cache de conversacion
    C->>MQ: Publica message.sent
    MQ-->>N: Entrega evento a notifications.queue
    N->>P: Crea notificacion persistente
    C-->>G: MessageResponse
    G-->>U1: 201 Created
```

### 2.4 Lectura de mensajes y presencia

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant G as API Gateway
    participant C as Chat Service
    participant M as MongoDB allora_chat
    participant R as Redis
    participant MQ as RabbitMQ

    U->>G: POST /chat/presence/online
    G->>C: Marca usuario online con X-User-Id
    C->>R: SET presence:{user_id} online con TTL
    C->>MQ: Publica user.online
    C-->>G: is_online=true
    G-->>U: Estado de presencia

    U->>G: POST /chat/conversations/{id}/read
    G->>C: Marca conversacion como leida
    C->>M: Actualiza mensajes recibidos a READ
    C->>R: Elimina unread counter
    C->>MQ: Publica messages.read
    C-->>G: Conteo de mensajes actualizados
    G-->>U: Confirmacion de lectura

    U->>G: POST /chat/presence/offline
    G->>C: Marca usuario offline
    C->>R: DELETE presence:{user_id}
    C->>MQ: Publica user.offline
    C-->>G: is_online=false
    G-->>U: Estado de presencia
```

### 2.5 Ubicacion en tiempo real por WebSocket

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant L as Location Service
    participant CM as ConnectionManager
    participant RM as RoomManager
    participant Peers as Usuarios en la misma sala

    U->>L: WS /ws/{user_id}?token=JWT
    L->>L: Resuelve identidad desde token o header Authorization
    L->>CM: Registra conexion WebSocket
    U->>L: Mensaje JSON {lat, lng, timestamp}
    L->>L: Valida LocationUpdate
    L->>CM: Guarda ultima ubicacion del usuario
    CM-->>Peers: Broadcast de ubicacion a usuarios de la sala

    U->>L: POST /api/v1/checkin
    L->>RM: Agrega usuario a room_id
    L->>CM: Asocia usuario con sala
    CM-->>Peers: Notifica user_joined

    U->>L: POST /api/v1/checkout
    L->>RM: Remueve usuario de room_id
    L->>CM: Remueve asociacion de sala
    CM-->>Peers: Notifica user_left
```

### 2.6 Match y notificacion asincrona

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant G as API Gateway
    participant MS as Match Service
    participant MQ as RabbitMQ
    participant N as Notification Service
    participant P as PostgreSQL
    participant C as Chat Service

    U->>G: POST /matches
    G->>G: Valida JWT
    G->>MS: Reenvia accion de match con X-User-Id
    MS->>MS: Evalua compatibilidad y reciprocidad
    MS->>MQ: Publica match.created
    MQ-->>N: Entrega evento match.created
    N->>P: Crea notificaciones para ambos usuarios
    MS-->>G: MatchResponse
    G-->>U: Match creado

    opt Habilitar conversacion despues del match
        MS->>C: Crear conversacion o permitir creacion posterior
        C->>MQ: Publica conversation.created
    end
```

---

## 3. Diagrama de eventos / event-driven architecture

```mermaid
flowchart TB
    subgraph Producers["Productores de eventos"]
        AuthP["Auth Service"]
        ChatP["Chat Service"]
        MatchP["Match Service"]
        LocationP["Location Service"]
    end

    subgraph Broker["RabbitMQ"]
        ExchangeGeneral["Topic Exchange<br/>allora.events"]
        ExchangeChat["Topic Exchange<br/>allora.chat.events"]
        NotificationsQueue["Durable Queue<br/>notifications.queue"]
        AuditQueue["Queue futura<br/>audit.queue"]
        AnalyticsQueue["Queue futura<br/>analytics.queue"]
    end

    subgraph Consumers["Consumidores"]
        NotificationC["Notification Service"]
        AuditC["Audit / Compliance<br/>futuro"]
        AnalyticsC["Analytics / Recomendaciones<br/>futuro"]
    end

    subgraph Stores["Persistencia derivada"]
        NotificationDB[("PostgreSQL<br/>notifications")]
        DataLake[("Storage analitico<br/>futuro")]
    end

    AuthP -->|"user.registered"| ExchangeGeneral
    ChatP -->|"conversation.created"| ExchangeChat
    ChatP -->|"message.sent"| ExchangeChat
    ChatP -->|"messages.read"| ExchangeChat
    ChatP -->|"user.online"| ExchangeChat
    ChatP -->|"user.offline"| ExchangeChat
    MatchP -->|"match.created"| ExchangeGeneral
    LocationP -.->|"location.updated / room.joined<br/>evento objetivo"| ExchangeGeneral

    ExchangeGeneral -->|"user.registered<br/>match.created<br/>signal.sent"| NotificationsQueue
    ExchangeChat -->|"message.sent"| NotificationsQueue
    ExchangeGeneral -.-> AuditQueue
    ExchangeChat -.-> AuditQueue
    ExchangeGeneral -.-> AnalyticsQueue
    ExchangeChat -.-> AnalyticsQueue

    NotificationsQueue --> NotificationC
    NotificationC --> NotificationDB
    AuditQueue -.-> AuditC
    AnalyticsQueue -.-> AnalyticsC
    AnalyticsC -.-> DataLake
```

