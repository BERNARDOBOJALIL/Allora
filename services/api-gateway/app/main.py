import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.auth_middleware import fetch_jwks, require_auth
from app.config import settings
from app.proxy_client import close_proxy_client, forward_request, get_proxy_client
from app.schemas import HealthResponse


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("api-gateway")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await fetch_jwks()
    except Exception as exc:
        logger.warning("JWKS startup load failed; will retry on protected requests: %s", exc)
    yield
    await close_proxy_client()


app = FastAPI(
    title="ALLORA API Gateway",
    lifespan=lifespan,
)

# Enable CORS for development (allow any origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PUBLIC_AUTH_PATHS = {
    "register",
    "login",
    "refresh",
}


SERVICE_CHECKS: dict[str, tuple[str, str, str]] = {
    "auth-service": ("http://auth-service:8000/health", "health", "Auth"),
    "chat-service": ("http://chat-service:8000/health", "health", "Chat"),
    "location-service": ("http://location-service:8003/api/v1/health", "status", "Location"),
}


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
        return HTMLResponse(
                """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Allora Mini Front</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f5f2eb;
            --panel: rgba(255, 255, 255, 0.86);
            --panel-border: rgba(25, 25, 25, 0.08);
            --text: #1f2937;
            --muted: #6b7280;
            --accent: #0f766e;
            --accent-2: #b45309;
            --danger: #b91c1c;
            --ok: #047857;
            --shadow: 0 18px 60px rgba(15, 23, 42, 0.12);
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: var(--text);
            background:
                radial-gradient(circle at top left, rgba(15, 118, 110, 0.18), transparent 34%),
                radial-gradient(circle at top right, rgba(180, 83, 9, 0.16), transparent 28%),
                linear-gradient(180deg, #fffdf8 0%, var(--bg) 100%);
        }

        .shell {
            width: min(1180px, calc(100% - 32px));
            margin: 0 auto;
            padding: 28px 0 40px;
        }

        .hero {
            display: grid;
            gap: 16px;
            grid-template-columns: 1.5fr 1fr;
            align-items: end;
            margin-bottom: 24px;
        }

        .title {
            margin: 0;
            font-size: clamp(2rem, 4vw, 3.6rem);
            line-height: 0.95;
            letter-spacing: -0.05em;
        }

        .subtitle {
            margin: 12px 0 0;
            max-width: 68ch;
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.55;
        }

        .status-bar {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            flex-wrap: wrap;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 14px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid var(--panel-border);
            box-shadow: var(--shadow);
            font-size: 0.92rem;
        }

        .dot {
            width: 10px;
            height: 10px;
            border-radius: 999px;
            background: #94a3b8;
        }

        .dot.ok { background: #16a34a; }
        .dot.warn { background: #f59e0b; }
        .dot.bad { background: #dc2626; }

        .grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
        }

        .card, .output {
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 24px;
            box-shadow: var(--shadow);
            backdrop-filter: blur(14px);
        }

        .card {
            padding: 18px;
        }

        .card h2,
        .output h2 {
            margin: 0 0 12px;
            font-size: 1.05rem;
            letter-spacing: -0.02em;
        }

        .muted { color: var(--muted); }

        .field {
            display: grid;
            gap: 6px;
            margin-bottom: 12px;
        }

        label {
            font-size: 0.88rem;
            color: #374151;
        }

        input, textarea, select, button {
            font: inherit;
        }

        input, textarea, select {
            width: 100%;
            border-radius: 14px;
            border: 1px solid rgba(148, 163, 184, 0.5);
            background: rgba(255, 255, 255, 0.9);
            color: var(--text);
            padding: 12px 14px;
            outline: none;
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }

        input:focus, textarea:focus, select:focus {
            border-color: rgba(15, 118, 110, 0.6);
            box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.12);
        }

        textarea {
            min-height: 120px;
            resize: vertical;
        }

        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 8px;
        }

        button {
            border: 0;
            border-radius: 14px;
            padding: 12px 16px;
            cursor: pointer;
            background: var(--accent);
            color: white;
            font-weight: 600;
            transition: transform 0.12s ease, opacity 0.12s ease;
        }

        button:hover { transform: translateY(-1px); }
        button.secondary { background: var(--accent-2); }
        button.ghost {
            background: rgba(255, 255, 255, 0.72);
            color: var(--text);
            border: 1px solid var(--panel-border);
        }

        button:disabled {
            opacity: 0.58;
            cursor: wait;
            transform: none;
        }

        .output {
            margin-top: 16px;
            padding: 18px;
        }

        pre {
            margin: 0;
            overflow: auto;
            padding: 16px;
            border-radius: 18px;
            background: #0f172a;
            color: #e2e8f0;
            font-size: 0.88rem;
            line-height: 1.5;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .span-2 { grid-column: span 2; }

        @media (max-width: 900px) {
            .hero, .grid { grid-template-columns: 1fr; }
            .span-2 { grid-column: span 1; }
            .status-bar { justify-content: flex-start; }
        }
    </style>
</head>
<body>
    <main class="shell">
        <section class="hero">
            <div>
                <h1 class="title">Allora Mini Front</h1>
                <p class="subtitle">
                    Interfaz mínima para probar el gateway, registrar un usuario, iniciar sesión y verificar que el backend responde.
                    Todo sale por el mismo origen, así que no necesitas tocar CORS para esta prueba.
                </p>
            </div>
            <div class="status-bar">
                <div class="pill"><span class="dot" id="health-dot"></span><span id="health-text">Health pendiente</span></div>
                <div class="pill"><span class="dot warn"></span><span id="token-state">Sin token</span></div>
            </div>
        </section>

        <section class="grid">
            <article class="card">
                <h2>Salud</h2>
                <p class="muted">Comprueba que el gateway está vivo.</p>
                            <article class="card span-2">
                                <h2>Servicios</h2>
                                <p class="muted">Estado agregado desde el gateway para ver rápidamente qué partes del backend responden.</p>
                                <div class="service-grid" id="service-grid">
                                    <div class="service-pill pending" data-service="auth-service">Auth: pendiente</div>
                                    <div class="service-pill pending" data-service="chat-service">Chat: pendiente</div>
                                    <div class="service-pill pending" data-service="location-service">Location: pendiente</div>
                                    <div class="service-pill pending" data-service="notification-service">Notifications: pendiente</div>
                                    <div class="service-pill neutral" data-service="match-service">Match: sin endpoint</div>
                                    <div class="service-pill neutral" data-service="user-service">User: sin endpoint</div>
                                </div>
                                <div class="actions" style="margin-top: 14px;">
                                    <button class="ghost" id="btn-services">Actualizar servicios</button>
                                </div>
                            </article>

                <div class="actions">
                    <button id="btn-health">Consultar /health</button>
                </div>
            </article>

            <article class="card">
                <h2>Registro rápido</h2>
                <div class="field">
                    <label for="register-name">Nombre</label>
                    <input id="register-name" value="Demo User" />
                </div>
                <div class="field">
                    <label for="register-email">Email</label>
                    <input id="register-email" type="email" value="demo@example.com" />
                </div>
                <div class="field">
                    <label for="register-phone">Teléfono</label>
                    <input id="register-phone" value="" placeholder="Opcional" />
                </div>
                <div class="field">
                    <label for="register-password">Password</label>
                    <input id="register-password" type="password" value="Password123!" />
                </div>
                <div class="actions">
                    <button class="secondary" id="btn-register">Registrar</button>
                </div>
            </article>

            <article class="card">
                <h2>Login</h2>
                <div class="field">
                    <label for="login-identifier">Email o teléfono</label>
                    <input id="login-identifier" value="demo@example.com" />
                </div>
                <div class="field">
                    <label for="login-password">Password</label>
                    <input id="login-password" type="password" value="Password123!" />
                </div>
                <div class="actions">
                    <button id="btn-login">Iniciar sesión</button>
                    <button class="ghost" id="btn-me">Probar /me</button>
                    <button class="ghost" id="btn-logout">Borrar token</button>
                </div>
            </article>

            <article class="card span-2">
                <h2>Chat rápido</h2>
                <p class="muted">Prueba crear conversación, listar y enviar mensajes por el gateway.</p>
                <div class="field">
                    <label for="chat-participant">Participant ID (user_id destino)</label>
                    <input id="chat-participant" placeholder="Pega aquí el user_id del otro usuario" />
                </div>
                <div class="field">
                    <label for="chat-conversation-id">Conversation ID</label>
                    <input id="chat-conversation-id" placeholder="Se autocompleta al crear/listar" />
                </div>
                <div class="field">
                    <label for="chat-message">Mensaje</label>
                    <input id="chat-message" value="Hola desde mini front" />
                </div>
                <div class="actions">
                    <button id="btn-chat-create">Crear conversación</button>
                    <button class="ghost" id="btn-chat-list">Listar conversaciones</button>
                    <button class="ghost" id="btn-chat-messages">Ver mensajes</button>
                    <button class="secondary" id="btn-chat-send">Enviar mensaje</button>
                    <button class="ghost" id="btn-chat-demo">Demo automático</button>
                </div>
            </article>

            <article class="card">
                <h2>Respuesta</h2>
                <p class="muted">Aquí verás el último JSON o error devuelto por el stack.</p>
                <div class="field">
                    <label for="request-body">Body personalizado opcional</label>
                    <textarea id="request-body" placeholder='{"example": true}'></textarea>
                </div>
                <div class="actions">
                    <button class="ghost" id="btn-clear">Limpiar salida</button>
                </div>
            </article>

            <article class="output span-2">
                <h2>Salida</h2>
                <pre id="output">Listo. Pulsa un botón para probar el backend.</pre>
            </article>
        </section>
    </main>

    <script>
        const output = document.getElementById("output");
        const healthDot = document.getElementById("health-dot");
        const healthText = document.getElementById("health-text");
        const tokenState = document.getElementById("token-state");
        const tokenKey = "allora_access_token";

        function setOutput(value) {
            output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
        }

        function setToken(token) {
            if (token) {
                localStorage.setItem(tokenKey, token);
                tokenState.textContent = "Token guardado";
            } else {
                localStorage.removeItem(tokenKey);
                tokenState.textContent = "Sin token";
            }
        }

        function getToken() {
            return localStorage.getItem(tokenKey);
        }

        function updateTokenState() {
            tokenState.textContent = getToken() ? "Token guardado" : "Sin token";
        }

        function requireToken() {
            const token = getToken();
            if (!token) {
                throw new Error("Primero inicia sesión para probar chat.");
            }
            return token;
        }

        function setConversationId(value) {
            document.getElementById("chat-conversation-id").value = value || "";
        }

        function getConversationId() {
            return document.getElementById("chat-conversation-id").value.trim();
        }

        async function requestAuthJson(url, options = {}) {
            const token = requireToken();
            return await requestJson(url, {
                ...options,
                headers: {
                    ...(options.headers || {}),
                    Authorization: `Bearer ${token}`,
                },
            });
        }

        function randomDemoEmail(prefix) {
            const base = Math.random().toString(36).slice(2, 8);
            return `${prefix}.${base}@example.com`;
        }
                        document.getElementById("btn-services").addEventListener("click", () => runAction(async () => {
                            await refreshServices();
                        }));

                        async function refreshServices() {
                            const data = await requestJson("/services/status");
                            for (const service of data.services) {
                                if (service.status === "ok") {
                                    setServiceStatus(service.name, "ok", `${service.label}: ok`);
                                } else if (service.status === "degraded") {
                                    setServiceStatus(service.name, "bad", `${service.label}: ${service.message}`);
                                } else {
                                    setServiceStatus(service.name, "neutral", `${service.label}: ${service.message}`);
                                }
                            }
                            setOutput(data);
                        }

                        function setServiceStatus(service, state, label) {
                            const pill = document.querySelector(`[data-service="${service}"]`);
                            if (!pill) {
                                return;
                            }

                            pill.className = `service-pill ${state}`;
                            pill.textContent = label;
                        }


        async function requestJson(url, options = {}) {
            const { headers: optionHeaders = {}, body: optionBody, ...restOptions } = options;
            const hasBody = optionBody !== undefined;
            const isJsonObject = hasBody
                && typeof optionBody === "object"
                && !(optionBody instanceof FormData)
                && !(optionBody instanceof URLSearchParams);

            const response = await fetch(url, {
                ...restOptions,
                headers: {
                    "Content-Type": "application/json",
                    ...optionHeaders,
                },
                body: isJsonObject ? JSON.stringify(optionBody) : optionBody,
            });

            const contentType = response.headers.get("content-type") || "";
            const payload = contentType.includes("application/json")
                ? await response.json()
                : await response.text();

            if (!response.ok) {
                const error = new Error("Request failed");
                error.status = response.status;
                error.payload = payload;
                throw error;
            }

            return payload;
        }

        async function runAction(handler) {
            const buttons = Array.from(document.querySelectorAll("button"));
            buttons.forEach((button) => (button.disabled = true));
            try {
                await handler();
            } catch (error) {
                setOutput({
                    error: error.message,
                    status: error.status || null,
                    detail: error.payload || null,
                });
            } finally {
                buttons.forEach((button) => (button.disabled = false));
                updateTokenState();
            }
        }

        document.getElementById("btn-health").addEventListener("click", () => runAction(async () => {
            const data = await requestJson("/health");
            healthDot.className = "dot ok";
            healthText.textContent = "Gateway OK";
            setOutput(data);
        }));

        document.getElementById("btn-register").addEventListener("click", () => runAction(async () => {
            const body = {
                nombre: document.getElementById("register-name").value.trim(),
                email: document.getElementById("register-email").value.trim() || null,
                telefono: document.getElementById("register-phone").value.trim() || null,
                password: document.getElementById("register-password").value,
            };

            const data = await requestJson("/auth/register", {
                method: "POST",
                body,
            });

            setOutput(data);
        }));

        document.getElementById("btn-login").addEventListener("click", () => runAction(async () => {
            const body = {
                identifier: document.getElementById("login-identifier").value.trim(),
                password: document.getElementById("login-password").value,
            };

            const data = await requestJson("/auth/login", {
                method: "POST",
                body,
            });

            setToken(data.access_token);
            setOutput(data);
        }));

        document.getElementById("btn-me").addEventListener("click", () => runAction(async () => {
            const token = getToken();
            if (!token) {
                throw new Error("Primero inicia sesión para obtener un token.");
            }

            const data = await requestJson("/me", {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });

            setOutput(data);
        }));

        document.getElementById("btn-chat-create").addEventListener("click", () => runAction(async () => {
            const participantId = document.getElementById("chat-participant").value.trim();
            if (!participantId) {
                throw new Error("Escribe un participant_id para crear conversación.");
            }

            const data = await requestAuthJson("/chat/conversations", {
                method: "POST",
                body: { participant_id: participantId },
            });

            setConversationId(data.id || "");
            setOutput(data);
        }));

        document.getElementById("btn-chat-list").addEventListener("click", () => runAction(async () => {
            const data = await requestAuthJson("/chat/conversations");
            if (Array.isArray(data) && data.length > 0 && data[0].id) {
                setConversationId(data[0].id);
            }
            setOutput(data);
        }));

        document.getElementById("btn-chat-messages").addEventListener("click", () => runAction(async () => {
            const conversationId = getConversationId();
            if (!conversationId) {
                throw new Error("Primero define conversation_id.");
            }

            const data = await requestAuthJson(`/chat/conversations/${conversationId}/messages`);
            setOutput(data);
        }));

        document.getElementById("btn-chat-send").addEventListener("click", () => runAction(async () => {
            const conversationId = getConversationId();
            const message = document.getElementById("chat-message").value.trim();
            if (!conversationId) {
                throw new Error("Primero define conversation_id.");
            }
            if (!message) {
                throw new Error("Escribe un mensaje.");
            }

            const data = await requestAuthJson(`/chat/conversations/${conversationId}/messages`, {
                method: "POST",
                body: { content: message },
            });
            setOutput(data);
        }));

        document.getElementById("btn-chat-demo").addEventListener("click", () => runAction(async () => {
            const originalToken = requireToken();
            const password = "Password123!";

            const receiverEmail = randomDemoEmail("receiver");
            await requestJson("/auth/register", {
                method: "POST",
                body: {
                    nombre: "Receiver Demo",
                    email: receiverEmail,
                    password,
                },
            });

            const receiverLogin = await requestJson("/auth/login", {
                method: "POST",
                body: {
                    identifier: receiverEmail,
                    password,
                },
            });

            const receiverId = receiverLogin?.user?.id;
            if (!receiverId) {
                throw new Error("No se pudo obtener user_id del usuario demo receptor.");
            }

            setToken(originalToken);
            document.getElementById("chat-participant").value = receiverId;

            const conversation = await requestAuthJson("/chat/conversations", {
                method: "POST",
                body: { participant_id: receiverId },
            });

            const conversationId = conversation?.id;
            setConversationId(conversationId || "");
            if (!conversationId) {
                throw new Error("No se pudo crear la conversación demo.");
            }

            const sent = await requestAuthJson(`/chat/conversations/${conversationId}/messages`, {
                method: "POST",
                body: { content: "Mensaje demo automático ✅" },
            });

            const messages = await requestAuthJson(`/chat/conversations/${conversationId}/messages`);

            setOutput({
                flow: "demo_chat_ok",
                receiver_email: receiverEmail,
                receiver_id: receiverId,
                conversation,
                sent_message: sent,
                messages,
            });
        }));

        document.getElementById("btn-logout").addEventListener("click", () => {
            setToken(null);
            setOutput("Token borrado.");
        });

        document.getElementById("btn-clear").addEventListener("click", () => {
            setOutput("Salida limpia.");
        });

        updateTokenState();
    </script>
</body>
</html>
                """
        )


@app.get("/services/status")
async def services_status() -> dict[str, Any]:
    client = await get_proxy_client()
    results: list[dict[str, Any]] = []

    async def probe(name: str, url: str, label: str) -> None:
        try:
            response = await client.get(url)
            response.raise_for_status()
            results.append(
                {
                    "name": name,
                    "label": label,
                    "status": "ok",
                    "message": "responde",
                    "details": response.json(),
                }
            )
        except httpx.HTTPError as exc:
            results.append(
                {
                    "name": name,
                    "label": label,
                    "status": "degraded",
                    "message": str(exc),
                }
            )

    for name, (url, _, label) in SERVICE_CHECKS.items():
        await probe(name, url, label)

    results.extend(
        [
            {
                "name": "notification-service",
                "label": "Notifications",
                "status": "unknown",
                "message": "pendiente de endpoint de health en esta versión",
            },
            {
                "name": "match-service",
                "label": "Match",
                "status": "unknown",
                "message": "sin endpoint de health en este workspace",
            },
            {
                "name": "user-service",
                "label": "User",
                "status": "unknown",
                "message": "sin endpoint de health en este workspace",
            },
        ]
    )

    return {"services": results}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(service="api-gateway", status="ok")


@app.get("/me")
async def me(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    return {
        "user_id": user["sub"],
        "email": user.get("email"),
        "token_payload": user,
    }


@app.api_route(
    "/auth/{path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def auth_proxy(path: str, request: Request):
    if path not in PUBLIC_AUTH_PATHS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ruta auth no publicada en el gateway",
        )
    return await forward_request(
        request,
        f"{settings.auth_service_url}/auth/{path}",
    )


# Protected auth-related endpoints (onboarding/profile-memory)
@app.api_route(
    "/auth/onboarding",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
@app.api_route(
    "/auth/onboarding/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def auth_onboarding_proxy(request: Request, path: str = "", user: dict[str, Any] = Depends(require_auth)):
    upstream_path = f"auth/onboarding/{path}" if path else "auth/onboarding"
    return await protected_proxy(request, settings.auth_service_url, upstream_path, user)


@app.api_route(
    "/auth/profile-memory",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
@app.api_route(
    "/auth/profile-memory/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def auth_profile_memory_proxy(request: Request, path: str = "", user: dict[str, Any] = Depends(require_auth)):
    upstream_path = f"auth/profile-memory/{path}" if path else "auth/profile-memory"
    return await protected_proxy(request, settings.auth_service_url, upstream_path, user)


async def protected_proxy(
    request: Request,
    service_url: str | None,
    upstream_path: str,
    user: dict[str, Any],
):
    if not service_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio no configurado",
        )
    return await forward_request(
        request,
        f"{service_url.rstrip('/')}/{upstream_path.lstrip('/')}",
        user_id=user["sub"],
    )


@app.api_route("/users/{user_id}/matches", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def user_potential_matches_proxy(
    user_id: str,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    return await protected_proxy(
        request,
        settings.matches_service_url,
        f"users/{user_id}/matches",
        user,
    )


@app.api_route("/users/{user_id}/all-matches", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def user_all_matches_proxy(
    user_id: str,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    return await protected_proxy(
        request,
        settings.matches_service_url,
        f"users/{user_id}/all-matches",
        user,
    )


@app.api_route("/users", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/users/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def users_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    return await protected_proxy(request, settings.users_service_url, path, user)


@app.post("/match")
async def match_sync_compat_proxy(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    if isinstance(payload, dict) and payload.get("user_a_id") and payload.get("user_b_id"):
        return await protected_proxy(request, settings.matches_service_url, "matches", user)

    return {
        "status": "ok",
        "mode": "match_profile_sync",
        "user_id": user["sub"],
        "received_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
    }


@app.api_route("/matches", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/matches/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/match", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/match/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def matches_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    upstream_path = f"matches/{path}" if path else "matches"
    return await protected_proxy(request, settings.matches_service_url, upstream_path, user)


@app.api_route("/chat", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/chat/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def chat_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    return await protected_proxy(request, settings.chat_service_url, path, user)


@app.api_route("/location", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/location/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def location_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    upstream_path = f"api/v1/{path}" if path else "api/v1"
    return await protected_proxy(request, settings.location_service_url, upstream_path, user)


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def location_compat_proxy(
    request: Request,
    path: str,
    user: dict[str, Any] = Depends(require_auth),
):
    # Compatibility route for clients that still call /api/v1/* on the gateway.
    upstream_path = f"api/v1/{path}"
    return await protected_proxy(request, settings.location_service_url, upstream_path, user)


@app.api_route("/profile", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/profile/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def profile_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    upstream_path = f"profile/{path}" if path else "profile"
    return await protected_proxy(request, settings.users_service_url, upstream_path, user)


@app.api_route("/preferences", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.api_route("/preferences/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def preferences_proxy(
    request: Request,
    path: str = "",
    user: dict[str, Any] = Depends(require_auth),
):
    upstream_path = f"preferences/{path}" if path else "preferences"
    return await protected_proxy(request, settings.users_service_url, upstream_path, user)
