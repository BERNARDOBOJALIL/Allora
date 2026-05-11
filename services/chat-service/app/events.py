import json
import logging
from datetime import datetime
from typing import Any

import aio_pika
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection, AbstractRobustExchange

from app.config import settings


logger = logging.getLogger("chat-service.events")
connection: AbstractRobustConnection | None = None
channel: AbstractRobustChannel | None = None
exchange: AbstractRobustExchange | None = None


def json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def connect_to_rabbitmq() -> None:
    global connection, channel, exchange
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        settings.chat_events_exchange,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )
    logger.info("RabbitMQ exchange ready: %s", settings.chat_events_exchange)


async def close_rabbitmq_connection() -> None:
    if connection:
        await connection.close()


async def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    if exchange is None:
        raise RuntimeError("RabbitMQ exchange has not been initialized")

    body = {
        "event_type": event_type,
        "payload": payload,
    }
    message = aio_pika.Message(
        body=json.dumps(body, default=json_default).encode("utf-8"),
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await exchange.publish(message, routing_key=event_type)
