# Location Service

Real-time user location updates and presence tracking microservice built with FastAPI and WebSockets.

## Features

- ✅ Real-time location tracking via WebSockets
- ✅ Virtual room-based presence system
- ✅ RESTful API for room and user management
- ✅ Structured logging
- ✅ Async/await architecture
- ✅ Dockerized deployment
- ✅ Health check endpoint
- ✅ Connection management and broadcast system
- ✅ Proximity-based user spaces (mini groups)
- ✅ Shared group chat integration through chat-service
- ✅ Space lifecycle rules (auto-expiration and auto-delete)

## Architecture

```
location-service/
├── main.py                 # FastAPI application entry point
├── app/
│   ├── config.py          # Configuration from environment
│   ├── logger.py          # Structured logging setup
│   ├── models.py          # Pydantic data models
│   ├── websocket_manager.py   # WebSocket connection management
│   ├── room_manager.py    # Virtual room management
│   └── api/
│       └── routes.py      # REST API endpoints
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container image
├── docker-compose.yml    # Multi-container orchestration
├── .env.example          # Environment variables template
├── test_client.py        # WebSocket test client
└── README.md            # This file
```

## Quick Start

### Local Development

1. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
```

4. **Run the service**
```bash
python main.py
```

The service will start at `http://localhost:8003`

### Docker Deployment

1. **Build image**
```bash
docker build -t location-service:1.0 .
```

2. **Run container**
```bash
docker run -p 8003:8003 \
  -e LOG_LEVEL=INFO \
  -e DEBUG=False \
  location-service:1.0
```

3. **Using Docker Compose**
```bash
docker-compose up -d location-service
```

## API Endpoints

### Health Check
```http
GET /api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "service": "location-service",
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

### Get Connected Users
```http
GET /api/v1/users
```

Response:
```json
{
  "connected_users": 5,
  "users": ["user1", "user2", "user3", "user4", "user5"]
}
```

### Get Active Rooms
```http
GET /api/v1/rooms
```

Response:
```json
{
  "active_rooms": 2,
  "rooms": {
    "room1": ["user1", "user2"],
    "room2": ["user3", "user4", "user5"]
  }
}
```

### Check In User to Room
```http
POST /api/v1/checkin
Content-Type: application/json

{
  "user_id": "user123",
  "room_id": "room1"
}
```

Response:
```json
{
  "status": "success",
  "message": "User user123 checked in to room room1",
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

### Check Out User from Room
```http
POST /api/v1/checkout
Content-Type: application/json

{
  "user_id": "user123",
  "room_id": "room1"
}
```

Response:
```json
{
  "status": "success",
  "message": "User user123 checked out from room room1",
  "timestamp": "2024-01-15T10:30:45.123456"
}

### Create Proximity Space
```http
POST /api/v1/spaces
Content-Type: application/json

{
  "user_id": "user123",
  "name": "Cafeteria Centro",
  "description": "Grupo para quienes estan cerca de la cafeteria",
  "photo_base64": "...",
  "lat": 19.4326,
  "lng": -99.1332,
  "radius_km": 1.5
}
```

Notes:
- The space creator is automatically added as first member.
- A shared group conversation is created in chat-service.

### List Nearby Spaces
```http
GET /api/v1/spaces/nearby?lat=19.4326&lng=-99.1332&radius_km=5
```

### Join Space (Proximity Required)
```http
POST /api/v1/spaces/{space_id}/join
Content-Type: application/json

{
  "user_id": "user456",
  "lat": 19.4330,
  "lng": -99.1330
}
```

Notes:
- Join is allowed only if user is inside the space radius.
- `lat/lng` can be omitted if user location is already being tracked over WebSocket.
- Joining also adds the user to the shared group chat in chat-service.

### Leave Space
```http
POST /api/v1/spaces/{space_id}/leave
Content-Type: application/json

{
  "user_id": "user456"
}
```

Lifecycle rules:
- If no one joins within 1 hour (only creator remains), the space is deleted.
- If a space had multiple members and then drops to only 1, it is deleted.
```

## WebSocket Endpoint

### Connect
```
ws://localhost:8003/ws/{user_id}
```

### Send Location Update
The WebSocket connection accepts JSON messages with location data:

```json
{
  "lat": 40.7128,
  "lng": -74.0060,
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

### Receive Broadcasts

**Location Update** (broadcast to users in same room):
```json
{
  "type": "location_update",
  "user_id": "user1",
  "room_id": "room1",
  "data": {
    "lat": 40.7128,
    "lng": -74.0060,
    "timestamp": "2024-01-15T10:30:45.123456"
  }
}
```

**User Joined**:
```json
{
  "type": "user_joined",
  "user_id": "user2",
  "room_id": "room1",
  "users_in_room": ["user1", "user2"]
}
```

**User Left**:
```json
{
  "type": "user_left",
  "user_id": "user2",
  "room_id": "room1",
  "users_in_room": ["user1"]
}
```

**Error**:
```json
{
  "type": "error",
  "message": "Invalid message format"
}
```

## Data Models

### LocationUpdate
```python
{
  "lat": float,
  "lng": float,
  "timestamp": str  # ISO format
}
```

### CheckinRequest
```python
{
  "user_id": str,
  "room_id": str
}
```

### CheckoutRequest
```python
{
  "user_id": str,
  "room_id": str
}
```

## Testing

### Run WebSocket Test Client
```bash
# Install test dependencies
pip install websockets httpx

# Run tests
python test_client.py
```

The test client will:
1. Test REST endpoints
2. Simulate 3 users connecting to WebSockets
3. Send location updates from each user
4. Receive broadcasted messages

### Manual Testing with cURL and WebSocket Client

**Health Check:**
```bash
curl http://localhost:8003/api/v1/health
```

**Get Users:**
```bash
curl http://localhost:8003/api/v1/users
```

**Check In User:**
```bash
curl -X POST http://localhost:8003/api/v1/checkin \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "room_id": "room1"}'
```

**WebSocket Connection** (using wscat or websocat):
```bash
# Install websocat
cargo install websocat

# Connect
websocat ws://localhost:8003/ws/user1

# Send message
{"lat": 40.7128, "lng": -74.0060, "timestamp": "2024-01-15T10:30:45.123456"}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICE_NAME` | location-service | Service name |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `HOST` | 0.0.0.0 | Server host |
| `PORT` | 8003 | Server port |
| `DEBUG` | False | Debug mode |
| `AUTH_JWT_SECRET` | change_this_secret | Shared secret used to validate auth-service tokens |
| `AUTH_JWT_ALGORITHM` | HS256 | JWT algorithm used by auth-service |
| `AUTH_SERVICE_URL` | http://auth-service:8000 | Auth service base URL for future remote checks |

### Create `.env` file
```bash
cp .env.example .env
# Edit .env with your values
```

## Logging

The service uses structured JSON logging:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "service": "location-service",
  "level": "INFO",
  "event": "__main__",
  "message": "User user1 connected. Total connections: 1"
}
```

Logs include:
- Timestamp (UTC ISO format)
- Service name
- Log level (DEBUG, INFO, WARNING, ERROR)
- Event type
- Message
- Error stack trace (if applicable)

## Auth Integration

`location-service` now links each location/session to the authenticated user ID from `auth-service`.

- REST endpoints accept a Bearer token in `Authorization`.
- `POST /api/v1/checkin` and `POST /api/v1/checkout` can use the token to derive `user_id` automatically.
- The WebSocket endpoint supports `?token=...` or `Authorization: Bearer ...` and validates that the token `sub` matches the path user id.

Example WebSocket URL:
```text
ws://localhost:8003/ws/user123?token=<access_token>
```

Example REST request:
```http
POST /api/v1/checkin
Authorization: Bearer <access_token>
Content-Type: application/json

{ "room_id": "room1" }
```

## Performance Considerations

- **In-Memory Storage**: Locations and connections are stored in memory. For production, consider Redis or database.
- **Broadcast System**: All messages to room users are sent serially. For large rooms, consider message queueing.
- **Connection Limits**: Testing with 1000+ concurrent connections may require OS-level tuning.

## Future Enhancements

- [ ] Redis integration for distributed deployments
- [ ] Message queue (RabbitMQ) for broadcasts
- [ ] Database persistence (PostgreSQL)
- [ ] Geospatial queries
- [ ] Room history/replay
- [ ] Connection authentication/authorization
- [ ] Metrics/monitoring (Prometheus)
- [ ] Clustering support

## Dependencies

- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **pydantic**: Data validation
- **python-dotenv**: Environment variables
- **websockets**: WebSocket protocol support (included in FastAPI)

## Error Handling

The service handles:
- Invalid JSON messages
- Connection drops
- Validation errors
- Missing rooms/users
- Concurrent operations

Errors are logged and appropriate error messages are sent to clients.

## Deployment

### Docker Compose
```yaml
location-service:
  build: ./services/location-service
  ports:
    - "8003:8003"
  environment:
    - LOG_LEVEL=INFO
    - DEBUG=False
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8003/api/v1/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### Production Checklist
- [ ] Set `DEBUG=False`
- [ ] Use production-grade logging (ELK Stack, CloudWatch)
- [ ] Enable authentication/authorization
- [ ] Use load balancer (Nginx, HAProxy)
- [ ] Set up monitoring (Prometheus, DataDog)
- [ ] Configure resource limits (memory, CPU)
- [ ] Use Redis for distributed sessions
- [ ] Enable HTTPS/WSS
- [ ] Implement rate limiting
- [ ] Add request tracing/correlation IDs

## License

MIT License

## Support

For issues or questions, please refer to the main project documentation.
