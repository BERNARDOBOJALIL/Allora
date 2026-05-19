from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import timedelta

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.database import close_mongo_connection, connect_to_mongo, get_database
from app.models import Plan, Role, VerificationPurpose, serialize_user, utc_now
from app.schemas import (
    AccessTokenResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MeUpdateRequest,
    MessageResponse,
    OAuthLoginRequest,
    OnboardingRequest,
    OnboardingResponse,
    ProfileMemoryResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
    VerifyPhoneRequest,
)
from app.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    generate_verification_code,
    hash_password,
    hash_secret,
    get_jwks,
    normalize_email,
    normalize_phone,
    verify_password,
)
import httpx


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(title="Allora Auth Service", version="0.1.0", lifespan=lifespan)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def build_user_response(
    user: dict,
    dev_codes: dict[str, str] | None = None,
    assistant_message: str | None = None,
    onboarding_state: dict | None = None,
) -> UserResponse:
    payload = serialize_user(user)
    if settings.dev_return_codes and dev_codes:
        payload["dev_codes"] = dev_codes
    if assistant_message is not None:
        payload["assistant_message"] = assistant_message
    if onboarding_state is not None:
        payload["onboarding_state"] = onboarding_state
    return UserResponse(**payload)


def identifier_query(identifier: str) -> dict:
    value = identifier.strip()
    if not value:
        return {"_id": None}
    return {
        "$or": [
            {"email": normalize_email(value)},
            {"telefono": normalize_phone(value)},
        ]
    }


async def find_user_by_identifier(
    db: AsyncIOMotorDatabase,
    identifier: str,
) -> dict | None:
    return await db.users.find_one(identifier_query(identifier))


async def ensure_identifier_available(
    db: AsyncIOMotorDatabase,
    email: str | None = None,
    telefono: str | None = None,
    exclude_user_id: ObjectId | None = None,
) -> None:
    clauses = []
    if email:
        clauses.append({"email": email})
    if telefono:
        clauses.append({"telefono": telefono})
    if not clauses:
        return

    query = {"$or": clauses}
    if exclude_user_id:
        query["_id"] = {"$ne": exclude_user_id}

    existing = await db.users.find_one(query)
    if not existing:
        return
    if email and existing.get("email") == email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ya registrado")
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Telefono ya registrado")


def require_active_user(user: dict) -> None:
    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")
    if user.get("is_blocked", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario bloqueado")


def merge_list_values(existing: list, incoming: list) -> list:
    merged: list = []
    seen: set[str] = set()
    for item in existing + incoming:
        if item is None:
            continue
        value = item.strip() if isinstance(item, str) else item
        if not value:
            continue
        key = str(value).lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(value)
    return merged


def merge_memory_dict(existing: dict | None, incoming: dict | None) -> dict:
    result = deepcopy(existing or {})
    if not incoming:
        return result

    for key, value in incoming.items():
        if value is None:
            continue
        current_value = result.get(key)
        if isinstance(value, list):
            current_list = current_value if isinstance(current_value, list) else []
            result[key] = merge_list_values(current_list, value)
        elif isinstance(value, dict):
            current_dict = current_value if isinstance(current_value, dict) else {}
            result[key] = merge_memory_dict(current_dict, value)
        else:
            result[key] = value
    return result


async def persist_profile_memory(
    db: AsyncIOMotorDatabase,
    user_id: str,
    memory_updates: dict | None,
) -> dict[str, dict]:
    updates = memory_updates or {}
    existing = await db.profiles.find_one({"user_id": user_id}) or {}

    profile_memory = merge_memory_dict(existing.get("profile_memory"), updates.get("profile_memory"))
    context_memory = merge_memory_dict(existing.get("context_memory"), updates.get("context_memory"))
    preference_memory = merge_memory_dict(existing.get("preference_memory"), updates.get("preference_memory"))

    await db.profiles.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "profile_memory": profile_memory,
                "context_memory": context_memory,
                "preference_memory": preference_memory,
                "updated_at": utc_now(),
            }
        },
        upsert=True,
    )

    return {
        "profile_memory": profile_memory,
        "context_memory": context_memory,
        "preference_memory": preference_memory,
    }


async def create_verification_code(
    db: AsyncIOMotorDatabase,
    purpose: VerificationPurpose,
    user_id: str | None = None,
    email: str | None = None,
    telefono: str | None = None,
) -> str:
    code = generate_verification_code()
    now = utc_now()
    await db.verification_codes.insert_one(
        {
            "user_id": user_id,
            "email": email,
            "telefono": telefono,
            "purpose": purpose.value,
            "code_hash": hash_secret(code),
            "expires_at": now + timedelta(minutes=settings.verification_code_expire_minutes),
            "used_at": None,
            "created_at": now,
        }
    )
    return code


async def issue_refresh_token(db: AsyncIOMotorDatabase, user_id: str) -> str:
    refresh_token = generate_refresh_token()
    now = utc_now()
    await db.refresh_tokens.insert_one(
        {
            "user_id": user_id,
            "token_hash": hash_secret(refresh_token),
            "expires_at": now + timedelta(days=settings.refresh_token_expire_days),
            "revoked_at": None,
            "created_at": now,
        }
    )
    return refresh_token


async def issue_token_pair(db: AsyncIOMotorDatabase, user: dict) -> TokenResponse:
    user_id = str(user["_id"])
    access_token, expires_in = create_access_token(
        user_id=user_id,
        role=user.get("role", Role.USER.value),
        plan=user.get("plan", Plan.FREE.value),
        email=user.get("email"),
        nombre=user.get("nombre"),
    )
    refresh_token = await issue_refresh_token(db, user_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=build_user_response(user),
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalido",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise credentials_error from exc

    user_id = payload.get("sub")
    if not ObjectId.is_valid(user_id):
        raise credentials_error

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise credentials_error
    require_active_user(user)
    return user


async def validate_verification_code(
    db: AsyncIOMotorDatabase,
    purpose: VerificationPurpose,
    code: str,
    user_id: str | None = None,
    email: str | None = None,
    telefono: str | None = None,
) -> dict:
    query = {
        "purpose": purpose.value,
        "code_hash": hash_secret(code),
        "used_at": None,
        "expires_at": {"$gt": utc_now()},
    }
    if user_id:
        query["user_id"] = user_id
    if email:
        query["email"] = email
    if telefono:
        query["telefono"] = telefono

    code_doc = await db.verification_codes.find_one(query, sort=[("created_at", -1)])
    if not code_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo invalido o expirado",
        )
    return code_doc


async def mark_code_as_used(db: AsyncIOMotorDatabase, code_id: ObjectId) -> None:
    await db.verification_codes.update_one(
        {"_id": code_id},
        {"$set": {"used_at": utc_now()}},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"service": "auth-service", "status": "ok"}


@app.get("/auth/.well-known/jwks.json")
async def jwks() -> dict[str, list[dict[str, str]]]:
    return get_jwks()


@app.post(
    "/auth/register",
    response_model=UserResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserResponse:
    await ensure_identifier_available(db, payload.email, payload.telefono)

    now = utc_now()
    user_doc = {
        "nombre": payload.nombre.strip(),
        "email": payload.email,
        "telefono": payload.telefono,
        "password_hash": hash_password(payload.password),
        "oauth_provider": None,
        "oauth_provider_id": None,
        "role": payload.role.value,
        "plan": payload.plan.value,
        "is_active": True,
        "is_email_verified": False,
        "is_phone_verified": False,
        "is_blocked": False,
        "created_at": now,
        "updated_at": now,
        "last_login": None,
        "password_changed_at": None,
    }

    try:
        result = await db.users.insert_one(user_doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email o telefono ya registrado",
        ) from exc

    user_doc["_id"] = result.inserted_id
    user_id = str(result.inserted_id)
    dev_codes = {}

    if payload.email:
        dev_codes["email"] = await create_verification_code(
            db,
            VerificationPurpose.EMAIL_VERIFY,
            user_id=user_id,
            email=payload.email,
        )
    if payload.telefono:
        dev_codes["telefono"] = await create_verification_code(
            db,
            VerificationPurpose.PHONE_VERIFY,
            user_id=user_id,
            telefono=payload.telefono,
        )

    # Initialize profile using external Allora agent (best-effort)
    assistant_message = None
    onboarding_state = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            agent_payload = {
                "user_id": user_id,
                "thread_id": f"onboarding-{user_id}",
                "message": (
                    f"Initialize profile for new user. Nombre: {user_doc.get('nombre')}; "
                    f"Email: {user_doc.get('email')}; Telefono: {user_doc.get('telefono')}"
                ),
            }
            resp = await client.post("https://alloraagent.onrender.com/chat", json=agent_payload)
            if resp.status_code == 200:
                data = resp.json()
                assistant_message = data.get("assistant_message")
                onboarding_state = data.get("conversation_state") or None
                await persist_profile_memory(db, user_id, data.get("memory_updates") or {})
    except Exception:
        # Best-effort: don't fail registration if external agent is unreachable
        pass

    return build_user_response(
        user_doc,
        dev_codes,
        assistant_message=assistant_message,
        onboarding_state=onboarding_state,
    )


@app.post("/auth/login", response_model=TokenResponse, response_model_exclude_none=True)
async def login(
    payload: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TokenResponse:
    user = await find_user_by_identifier(db, payload.identifier)
    if not user or not verify_password(payload.password, user.get("password_hash")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
        )

    require_active_user(user)
    now = utc_now()
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": now, "updated_at": now}},
    )
    user["last_login"] = now
    user["updated_at"] = now
    return await issue_token_pair(db, user)


@app.post("/auth/refresh", response_model=AccessTokenResponse)
async def refresh_token(
    payload: RefreshRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AccessTokenResponse:
    token_doc = await db.refresh_tokens.find_one({"token_hash": hash_secret(payload.refresh_token)})
    if (
        not token_doc
        or token_doc.get("revoked_at") is not None
        or token_doc["expires_at"] <= utc_now()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalido",
        )

    if not ObjectId.is_valid(token_doc["user_id"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario invalido")

    user = await db.users.find_one({"_id": ObjectId(token_doc["user_id"])})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario invalido")
    require_active_user(user)

    access_token, expires_in = create_access_token(
        user_id=str(user["_id"]),
        role=user.get("role", Role.USER.value),
        plan=user.get("plan", Plan.FREE.value),
        email=user.get("email"),
        nombre=user.get("nombre"),
    )
    return AccessTokenResponse(access_token=access_token, token_type="bearer", expires_in=expires_in)


@app.post("/auth/logout", response_model=MessageResponse, response_model_exclude_none=True)
async def logout(
    payload: LogoutRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    await db.refresh_tokens.update_one(
        {"token_hash": hash_secret(payload.refresh_token), "revoked_at": None},
        {"$set": {"revoked_at": utc_now()}},
    )
    return MessageResponse(message="Sesion cerrada")


@app.get("/auth/me", response_model=UserResponse, response_model_exclude_none=True)
async def me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return build_user_response(current_user)


@app.put("/auth/me", response_model=UserResponse, response_model_exclude_none=True)
async def update_me(
    payload: MeUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserResponse:
    requested = payload.model_fields_set
    new_email = current_user.get("email")
    new_phone = current_user.get("telefono")

    if "email" in requested:
        new_email = payload.email
    if "telefono" in requested:
        new_phone = payload.telefono
    if not new_email and not new_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe existir al menos email o telefono",
        )

    await ensure_identifier_available(
        db,
        email=new_email if new_email != current_user.get("email") else None,
        telefono=new_phone if new_phone != current_user.get("telefono") else None,
        exclude_user_id=current_user["_id"],
    )

    updates = {"updated_at": utc_now()}
    dev_codes = {}

    if "nombre" in requested and payload.nombre is not None:
        updates["nombre"] = payload.nombre.strip()
    if "email" in requested and new_email != current_user.get("email"):
        updates["email"] = new_email
        updates["is_email_verified"] = False
    if "telefono" in requested and new_phone != current_user.get("telefono"):
        updates["telefono"] = new_phone
        updates["is_phone_verified"] = False

    await db.users.update_one({"_id": current_user["_id"]}, {"$set": updates})
    updated_user = await db.users.find_one({"_id": current_user["_id"]})

    if "email" in updates and updated_user.get("email"):
        dev_codes["email"] = await create_verification_code(
            db,
            VerificationPurpose.EMAIL_VERIFY,
            user_id=str(updated_user["_id"]),
            email=updated_user["email"],
        )
    if "telefono" in updates and updated_user.get("telefono"):
        dev_codes["telefono"] = await create_verification_code(
            db,
            VerificationPurpose.PHONE_VERIFY,
            user_id=str(updated_user["_id"]),
            telefono=updated_user["telefono"],
        )

    return build_user_response(updated_user, dev_codes)


@app.put(
    "/auth/change-password",
    response_model=MessageResponse,
    response_model_exclude_none=True,
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    if not verify_password(payload.current_password, current_user.get("password_hash")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contrasena actual invalida",
        )

    now = utc_now()
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(payload.new_password),
                "password_changed_at": now,
                "updated_at": now,
            }
        },
    )
    return MessageResponse(message="Contrasena actualizada")


@app.post(
    "/auth/forgot-password",
    response_model=MessageResponse,
    response_model_exclude_none=True,
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    query_parts = []
    if payload.email:
        query_parts.append({"email": payload.email})
    if payload.telefono:
        query_parts.append({"telefono": payload.telefono})

    user = await db.users.find_one({"$or": query_parts}) if query_parts else None
    code = None

    if user and user.get("is_active", True) and not user.get("is_blocked", False):
        email = payload.email if payload.email == user.get("email") else None
        telefono = payload.telefono if payload.telefono == user.get("telefono") else None
        code = await create_verification_code(
            db,
            VerificationPurpose.PASSWORD_RESET,
            user_id=str(user["_id"]),
            email=email,
            telefono=telefono,
        )

    return MessageResponse(
        message="Si la cuenta existe, se generara un codigo de recuperacion",
        dev_code=code if settings.dev_return_codes and code else None,
    )


@app.post(
    "/auth/reset-password",
    response_model=MessageResponse,
    response_model_exclude_none=True,
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    user = await find_user_by_identifier(db, payload.identifier)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo invalido o expirado",
        )

    value = payload.identifier.strip()
    email = normalize_email(value) if normalize_email(value) == user.get("email") else None
    telefono = normalize_phone(value) if normalize_phone(value) == user.get("telefono") else None

    code_doc = await validate_verification_code(
        db,
        VerificationPurpose.PASSWORD_RESET,
        payload.code,
        user_id=str(user["_id"]),
        email=email,
        telefono=telefono,
    )
    await mark_code_as_used(db, code_doc["_id"])

    now = utc_now()
    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(payload.new_password),
                "password_changed_at": now,
                "updated_at": now,
            }
        },
    )
    return MessageResponse(message="Contrasena restablecida")


@app.post(
    "/auth/verify-email",
    response_model=MessageResponse,
    response_model_exclude_none=True,
)
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    user = await db.users.find_one({"email": payload.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo invalido o expirado",
        )

    code_doc = await validate_verification_code(
        db,
        VerificationPurpose.EMAIL_VERIFY,
        payload.code,
        user_id=str(user["_id"]),
        email=payload.email,
    )
    await mark_code_as_used(db, code_doc["_id"])
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_email_verified": True, "updated_at": utc_now()}},
    )
    return MessageResponse(message="Email verificado")


@app.post(
    "/auth/verify-phone",
    response_model=MessageResponse,
    response_model_exclude_none=True,
)
async def verify_phone(
    payload: VerifyPhoneRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    user = await db.users.find_one({"telefono": payload.telefono})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo invalido o expirado",
        )

    code_doc = await validate_verification_code(
        db,
        VerificationPurpose.PHONE_VERIFY,
        payload.code,
        user_id=str(user["_id"]),
        telefono=payload.telefono,
    )
    await mark_code_as_used(db, code_doc["_id"])
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_phone_verified": True, "updated_at": utc_now()}},
    )
    return MessageResponse(message="Telefono verificado")


@app.post("/auth/oauth/login", response_model=TokenResponse, response_model_exclude_none=True)
async def oauth_login(
    payload: OAuthLoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TokenResponse:
    user = await db.users.find_one(
        {
            "oauth_provider": payload.provider,
            "oauth_provider_id": payload.provider_user_id,
        }
    )

    if not user:
        if payload.email and await db.users.find_one({"email": payload.email}):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email ya registrado con otro metodo de acceso",
            )

        now = utc_now()
        user_doc = {
            "nombre": (payload.nombre or payload.email or payload.provider).strip(),
            "email": payload.email,
            "telefono": None,
            "password_hash": None,
            "oauth_provider": payload.provider,
            "oauth_provider_id": payload.provider_user_id,
            "role": Role.USER.value,
            "plan": Plan.FREE.value,
            "is_active": True,
            "is_email_verified": bool(payload.email),
            "is_phone_verified": False,
            "is_blocked": False,
            "created_at": now,
            "updated_at": now,
            "last_login": now,
            "password_changed_at": None,
        }
        try:
            result = await db.users.insert_one(user_doc)
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuario OAuth ya registrado",
            ) from exc
        user_doc["_id"] = result.inserted_id
        user = user_doc
    else:
        require_active_user(user)
        now = utc_now()
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": now, "updated_at": now}},
        )
        user["last_login"] = now
        user["updated_at"] = now

    return await issue_token_pair(db, user)



@app.get(
    "/auth/profile-memory/{user_id}",
    response_model=ProfileMemoryResponse,
    response_model_exclude_none=True,
)
async def get_profile_memory(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ProfileMemoryResponse:
    # Only allow users to fetch their own profile memory
    if str(current_user.get("_id")) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    doc = await db.profiles.find_one({"user_id": user_id}) or {}

    return ProfileMemoryResponse(
        user_id=user_id,
        profile_memory=doc.get("profile_memory") or {},
        context_memory=doc.get("context_memory") or {},
        preference_memory=doc.get("preference_memory") or {},
        updated_at=doc.get("updated_at"),
    )


@app.post(
    "/auth/onboarding/{user_id}",
    response_model=OnboardingResponse,
    response_model_exclude_none=True,
)
async def post_onboarding_message(
    user_id: str,
    payload: OnboardingRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> OnboardingResponse:
    # Only allow users to act on their own onboarding thread
    if str(current_user.get("_id")) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    thread_id = payload.thread_id or f"onboarding-{user_id}"
    assistant_message = None
    memory_updates = None
    conversation_state = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            agent_payload = {"user_id": user_id, "thread_id": thread_id, "message": payload.message}
            resp = await client.post("https://alloraagent.onrender.com/chat", json=agent_payload)
            if resp.status_code == 200:
                data = resp.json()
                assistant_message = data.get("assistant_message")
                memory_updates = data.get("memory_updates") or {}
                conversation_state = data.get("conversation_state") or None
                await persist_profile_memory(db, user_id, memory_updates)
    except Exception:
        # Best-effort: don't fail the request if the agent is unreachable
        pass

    return OnboardingResponse(
        assistant_message=assistant_message,
        memory_updates=memory_updates,
        conversation_state=conversation_state,
    )
