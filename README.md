# Allora

> Plataforma SaaS enfocada en conexiones sociales más naturales mediante interacción progresiva, tiempo real y arquitectura de microservicios distribuidos.

---

# Integrantes

| Nombre | Rol |
|---|---|
| Bernardo Bojalil Lorenzini | Architecture Developer |
| Emiliano Montoya Velázquez | Frontend Developer |
| Jesus Manuel Ruiz Fuentes | DevOps |
| Roberto Villegas Ojeda | Backend Developer |

---

# Descripción del Proyecto

Muchas personas actualmente tienen dificultades al momento de generar interacciones sociales reales debido a la incomodidad, miedo al rechazo y prejuicios basados únicamente en la apariencia física.

Aplicaciones tradicionales como Tinder o Bumble utilizan modelos basados en *swipes* y perfiles superficiales, donde las decisiones se toman principalmente por fotografías y descripciones rápidas.

**Allora** propone una alternativa basada en interacción progresiva asistida por IA, permitiendo que las conexiones surjan a partir de intereses compartidos, presencia en tiempo real e interacción natural entre usuarios que coinciden en lugar y momento.

---

# Arquitectura General

## Diagrama General

```mermaid
flowchart LR

    %% CLIENTE
    Client["Cliente Web / Mobile / Postman"]

    %% =========================
    %% API GATEWAY
    %% =========================
    subgraph Edge["Entrada al Sistema"]
        Gateway["API Gateway<br/>FastAPI<br/>:8000"]
    end

    %% =========================
    %% SERVICIOS
    %% =========================
    subgraph Backend["Servicios Backend"]

        Auth["Auth Service<br/>Usuarios, Login y JWT<br/>:8001"]

        Match["Match Service<br/>Sistema de Matches<br/>:8002"]

        Location["Location Service<br/>Ubicación y WebSockets<br/>:8003"]

        Notifications["Notification Service<br/>Gestión de Notificaciones<br/>:8004"]

        Users["User Service<br/>Perfil y Preferencias<br/>:8005"]

        Chat["Chat Service<br/>Conversaciones y Mensajes<br/>:8006"]

    end

    %% =========================
    %% BASES DE DATOS
    %% =========================
    subgraph Data["Persistencia y Estado"]

        MongoAuth[("MongoDB<br/>allora_auth")]

        MongoChat[("MongoDB<br/>allora_chat")]

        NotificationDB[("PostgreSQL<br/>Notificaciones")]

        Redis[("Redis<br/>Presencia<br/>Unread Counters<br/>Cache Temporal")]

    end

    %% =========================
    %% EVENT BUS
    %% =========================
    subgraph Messaging["Mensajería Asíncrona"]

        Rabbit["RabbitMQ<br/>Topic Exchanges / Queues"]

    end

    %% =========================
    %% CONEXIONES CLIENTE
    %% =========================
    Client -->|REST / HTTP| Gateway
    Client -->|WebSocket Tiempo Real| Location

    %% =========================
    %% ROUTING GATEWAY
    %% =========================
    Gateway -->|/auth/*| Auth
    Gateway -->|JWT + X-User-Id| Chat
    Gateway -->|JWT + X-User-Id| Match
    Gateway -->|JWT + X-User-Id| Location
    Gateway -->|JWT + X-User-Id| Users

    %% =========================
    %% PERSISTENCIA
    %% =========================
    Auth --> MongoAuth

    Chat --> MongoChat
    Chat --> Redis

    Notifications --> NotificationDB

    Gateway -->|Validación JWT / JWKS| Auth

    %% =========================
    %% EVENTOS
    %% =========================
    Chat -->|conversation.created| Rabbit
    Chat -->|message.sent| Rabbit
    Chat -->|message.read| Rabbit
    Chat -->|user.online| Rabbit
    Chat -->|user.offline| Rabbit

    Match -->|match.created| Rabbit

    Auth -->|user.registered| Rabbit

    Rabbit -->|Consume eventos| Notifications
```

---

# Flujo Completo de la Aplicación

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
    participant DB as Bases de Datos

    %% =========================
    %% AUTENTICACION
    %% =========================
    U->>G: POST /auth/register o /auth/login
    G->>A: Reenvía solicitud pública

    A->>DB: Guarda usuario, tokens y códigos

    A-->>G: JWT + Refresh Token
    G-->>U: Respuesta autenticada

    %% =========================
    %% VALIDACION JWT
    %% =========================
    U->>G: Request protegida con Bearer JWT

    G->>A: Consulta JWKS / valida token
    A-->>G: Token válido

    %% =========================
    %% CREACION CONVERSACION
    %% =========================
    U->>G: POST /chat/conversations
    G->>C: Crear conversación

    C->>DB: Guarda conversación en MongoDB
    C->>R: Cachea datos de conversación

    C->>MQ: Publica conversation.created

    C-->>G: Conversación creada
    G-->>U: Respuesta exitosa

    %% =========================
    %% ENVIO MENSAJE
    %% =========================
    U->>G: POST /chat/conversations/{id}/messages

    G->>C: Enviar mensaje

    C->>DB: Guarda mensaje
    C->>R: Incrementa unread counter

    C->>MQ: Publica message.sent

    MQ->>N: Consume message.sent
    N->>DB: Crea notificación

    C-->>G: Mensaje enviado
    G-->>U: Respuesta exitosa

    %% =========================
    %% PRESENCIA
    %% =========================
    U->>G: POST /chat/presence/online

    G->>C: Usuario online

    C->>R: Guarda presencia con TTL
    C->>MQ: Publica user.online

    %% =========================
    %% WEBSOCKET
    %% =========================
    U->>L: WebSocket /ws/{user_id}

    L->>L: Administra salas y ubicación
    L-->>U: Broadcast en tiempo real

    %% =========================
    %% MATCHES
    %% =========================
    U->>G: Acción de match

    G->>M: Reenvía solicitud
    M->>DB: Guarda match

    M->>MQ: Publica match.created

    MQ->>N: Consume match.created
    N->>DB: Genera notificación
```

---

# Tecnologías Utilizadas

| Tecnología | Uso |
|---|---|
| Python | Lenguaje principal de desarrollo |
| FastAPI | APIs REST y microservicios |
| Uvicorn | Servidor ASGI |
| Docker | Contenedorización y despliegue local |
| MongoDB | Persistencia principal |
| Redis | Cache y estados temporales |
| RabbitMQ | Comunicación asíncrona |
| PostgreSQL | Persistencia de notificaciones |
| WebSockets | Comunicación en tiempo real |
| CORS | Comunicación frontend-backend |

---

# Servicios

| Servicio | Puerto | Responsabilidad |
|---|---|---|
| API Gateway | 8000 | Entrada principal y routing |
| Auth Service | 8001 | Autenticación y JWT |
| Match Service | 8002 | Matches entre usuarios |
| Location Service | 8003 | Ubicación en tiempo real |
| Notification Service | 8004 | Gestión de notificaciones |
| User Service | 8005 | Perfil y preferencias |
| Chat Service | 8006 | Conversaciones y mensajes |

---

# Instalación

## Clonar repositorio

```bash
git clone https://github.com/BERNARDOBOJALIL/Allora.git

cd Allora
```

---

## Configurar variables de entorno

```bash
cp .env.example .env
```

---

## Levantar servicios

```bash
docker compose up --build
```

---

# Frontend

## Expo Go

Escanear el código QR generado por Expo o acceder desde:

```txt
http://localhost:8081
```

---

# Variables de Entorno

```env
# MongoDB
MONGO_URI=mongodb://mongodb:27017
MONGO_DB_NAME=allora_auth
CHAT_MONGO_DB_NAME=allora_chat

# Redis
REDIS_URL=redis://redis:6379/0

# RabbitMQ
RABBITMQ_DEFAULT_USER=guest
RABBITMQ_DEFAULT_PASS=guest
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/

CHAT_EVENTS_EXCHANGE=allora.chat.events
CHAT_SERVICE_URL=http://chat-service:8000

# JWT
JWT_SECRET=change_this_secret
JWT_ALGORITHM=RS256
JWT_EXPIRE_MINUTES=60
JWT_ISSUER=auth-service
JWT_KEY_ID=allora-auth-key-1

# Tokens y códigos
REFRESH_TOKEN_EXPIRE_DAYS=30
VERIFICATION_CODE_EXPIRE_MINUTES=10
DEV_RETURN_CODES=false
```

---

# Endpoints Principales

## API Gateway

| Endpoint | Descripción |
|---|---|
| GET /health | Estado del gateway |
| GET /services/status | Estado de servicios internos |
| /auth/{path} | Proxy hacia auth-service |
| /chat/{path} | Proxy hacia chat-service |
| /location/{path} | Proxy hacia location-service |

---

## Auth Service

| Endpoint | Descripción |
|---|---|
| POST /auth/register | Registrar usuario |
| POST /auth/login | Iniciar sesión |
| POST /auth/logout | Cerrar sesión |
| GET /auth/me | Obtener usuario autenticado |
| PUT /auth/me | Actualizar usuario |
| PUT /auth/change-password | Cambiar contraseña |
| POST /auth/forgot-password | Recuperación de contraseña |
| POST /auth/reset-password | Restablecer contraseña |
| POST /auth/verify-email | Verificar email |
| POST /auth/verify-phone | Verificar teléfono |

---

## Chat Service

| Endpoint | Descripción |
|---|---|
| POST /conversations | Crear conversación |
| GET /conversations | Obtener conversaciones |
| GET /conversations/{conversation_id}/messages | Obtener mensajes |
| POST /conversations/{conversation_id}/messages | Enviar mensaje |
| POST /conversations/{conversation_id}/read | Marcar mensajes leídos |
| POST /presence/online | Usuario online |
| POST /presence/offline | Usuario offline |
| GET /presence/{target_user_id} | Estado de presencia |

---

## Location Service

| Endpoint | Descripción |
|---|---|
| GET /api/v1/users | Usuarios conectados |
| GET /api/v1/rooms | Salas activas |
| POST /api/v1/checkin | Entrar a sala |
| POST /api/v1/checkout | Salir de sala |
| GET /api/v1/nearby | Usuarios cercanos |
| WS /ws/{user_id} | WebSocket en tiempo real |

---

## Notification Service

| Endpoint | Descripción |
|---|---|
| GET /notifications/{user_id} | Obtener notificaciones |
| PATCH /notifications/read | Marcar notificación como leída |

---

# Eventos Principales

| Evento | Descripción |
|---|---|
| conversation.created | Conversación creada |
| message.sent | Mensaje enviado |
| message.read | Mensaje leído |
| user.online | Usuario conectado |
| user.offline | Usuario desconectado |
| match.created | Match generado |
| user.registered | Usuario registrado |

---

# Evidencia de Pruebas

- Validación de autenticación JWT
- Comunicación entre microservicios
- Publicación y consumo de eventos RabbitMQ
- Persistencia en MongoDB y PostgreSQL
- Manejo de cache y presencia con Redis
- Comunicación en tiempo real mediante WebSockets

---

# Experiencias Aprendidas

> — Roberto Villegas:Trabajar en mi proyecto de sistemas distribuidos me permitió tener un acercamiento más real a cómo funciona un entorno profesional de desarrollo de software. Aprendí la importancia de documentar correctamente el trabajo y utilizar control de versiones para facilitar la integración de servicios. También comprendí la relevancia de realizar pruebas E2E y unitarias para validar el funcionamiento del sistema, además de aprender a desarrollar funcionalidades con manejo de estados dinámicos y procesos que cambian constantemente.







