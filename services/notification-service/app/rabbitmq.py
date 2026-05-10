import json
import aio_pika
from app.config import settings
from app.services.notification_service import NotificationService

async def start_consumer():
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    # declarar exchange (topic)
    exchange = await channel.declare_exchange(
        "allora.events",
        aio_pika.ExchangeType.TOPIC,
        durable=True
    )
    # Crear cola para este servicio
    queue = await channel.declare_queue("notifications.queue", durable=True)
    # routing keys par eventos
    routing_keys = [
        "signal.sent",
        # "match.created",
        # "user.registered",
        # "message.sent"
    ]
    for key in routing_keys:
        await queue.bind(exchange, routing_key=key)

    async def process_message(message: aio_pika.IncomingMessage):
        async with message.process():
            body = json.loads(message.body.decode())
            event_type = message.routing_key
            print(f"Evento recibido: {event_type} - {body}")
            await NotificationService.handle_event(event_type, body)

    await queue.consume(process_message)
    print("Notification service consumiendo eventos...")
    return connection