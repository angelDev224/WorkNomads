import json

import aio_pika
import structlog

from app.config import settings

logger = structlog.get_logger()
_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None


async def get_channel() -> aio_pika.abc.AbstractChannel:
    global _connection, _channel
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    if _channel is None or _channel.is_closed:
        _channel = await _connection.channel()
        await _channel.declare_queue(settings.classification_queue, durable=True)
    return _channel


async def publish_classification_task(submission_id: str, photo_key: str) -> None:
    channel = await get_channel()
    body = json.dumps({"submission_id": submission_id, "photo_key": photo_key}).encode()
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=settings.classification_queue,
    )
    logger.info("classification task published", submission_id=submission_id)


async def close_messaging() -> None:
    global _connection, _channel
    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()
    _connection = None
    _channel = None
