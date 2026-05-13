API Gateway
--------------

Lightweight FastAPI-based gateway that proxies HTTP requests to `location-service` and relays WebSocket connections.

Run locally (use the workspace virtualenv):

```powershell
cd services/api-gateway
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Integration test (assumes `location-service` running on 127.0.0.1:8003):

```powershell
python test_integration.py
```
