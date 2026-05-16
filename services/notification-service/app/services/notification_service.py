from sqlalchemy import select, update
from app.db import AsyncSessionLocal
from app.models import Notification
from app.schemas import NotificationResponse
from typing import List, Dict, Any

class NotificationService:

    @staticmethod
    async def create_notification(
        user_id: str,
        type: str,
        title: str,
        body: str,
        extra_data: Dict[str, Any] = None
    ) -> Notification:
        async with AsyncSessionLocal() as session:
            notif = Notification(
                user_id=user_id,
                type=type,
                title=title,
                body=body,
                extra_data=extra_data
            )
            session.add(notif)
            await session.commit()
            await session.refresh(notif)
            return notif

    @staticmethod
    async def get_user_notifications(
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[NotificationResponse]:
        async with AsyncSessionLocal() as session:
            stmt = select(Notification).where(
                Notification.user_id == user_id
            ).order_by(Notification.created_at.desc()).offset(offset).limit(limit)
            result = await session.execute(stmt)
            notifications = result.scalars().all()
            return [NotificationResponse.model_validate(n) for n in notifications]

    @staticmethod
    async def mark_as_read(notification_id: str) -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Notification)
                .where(Notification.id == notification_id)
                .values(read=True)
            )
            await session.commit()

    @staticmethod
    async def handle_event(event_type: str, payload: dict):
        # signal.sent
        if event_type == "signal.sent":
            to_user_id = payload.get("to_user_id")
            from_user_name = payload.get("from_user_name", "Alguien")
            place_name = payload.get("place_name", "un lugar")
            if to_user_id:
                await NotificationService.create_notification(
                    user_id=to_user_id,
                    type="signal_sent",
                    title="¡Alguien está interesado!",
                    body=f"{from_user_name} te ha enviado una señal en {place_name}.",
                    extra_data={
                        "from_user_id": payload.get("from_user_id"),
                        "place_id": payload.get("place_id")
                    }
                )

        # message.sent -> notify recipient about new message
        if event_type == "message.sent":
            # payload expected to contain: to_user_id, from_user_id, from_user_name, content, conversation_id
            to_user_id = payload.get("to_user_id")
            from_user_name = payload.get("from_user_name", "Alguien")
            content = payload.get("content", "")
            summary = (content[:120] + "...") if len(content) > 120 else content
            if to_user_id:
                await NotificationService.create_notification(
                    user_id=to_user_id,
                    type="message_sent",
                    title="Nuevo mensaje",
                    body=f"{from_user_name}: {summary}",
                    extra_data={
                        "from_user_id": payload.get("from_user_id"),
                        "conversation_id": payload.get("conversation_id"),
                    }
                )

        # match.created -> notify both users about match
        if event_type == "match.created":
            user_a = payload.get("user_a")
            user_b = payload.get("user_b")
            match_id = payload.get("match_id")
            if user_a:
                await NotificationService.create_notification(
                    user_id=user_a,
                    type="match_created",
                    title="¡Tienes un match!",
                    body="Has hecho match con alguien. ¡Empieza a chatear!",
                    extra_data={"match_id": match_id, "other_user": user_b}
                )
            if user_b:
                await NotificationService.create_notification(
                    user_id=user_b,
                    type="match_created",
                    title="¡Tienes un match!",
                    body="Has hecho match con alguien. ¡Empieza a chatear!",
                    extra_data={"match_id": match_id, "other_user": user_a}
                )

        # user.registered -> welcome notification
        if event_type == "user.registered":
            user_id = payload.get("user_id")
            if user_id:
                await NotificationService.create_notification(
                    user_id=user_id,
                    type="user_registered",
                    title="Bienvenido a Allora",
                    body="Gracias por registrarte — completa tu perfil para conseguir mejores matches.",
                    extra_data={}
                )
        # añadir otros eventos para despues