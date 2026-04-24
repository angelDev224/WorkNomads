import asyncio
import json
import uuid
from datetime import datetime, timezone

import aio_pika
import structlog
from sqlalchemy import select, update

from app.classifier import classify
from app.config import settings
from app.db.models import Result, Submission
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger()


async def process_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process(requeue=True):
        try:
            body = json.loads(message.body)
            submission_id = body["submission_id"]
            photo_key = body["photo_key"]
        except (KeyError, json.JSONDecodeError) as exc:
            logger.error("malformed message", error=str(exc))
            return

        logger.info("classifying", submission_id=submission_id)
        try:
            result = classify(photo_key)
        except Exception as exc:
            logger.error("classification failed", submission_id=submission_id, error=str(exc))
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Submission)
                    .where(Submission.id == uuid.UUID(submission_id))
                    .values(status="error", updated_at=datetime.now(timezone.utc))
                )
                await db.commit()
            return

        async with AsyncSessionLocal() as db:
            # Upsert result
            existing = await db.execute(
                select(Result).where(Result.submission_id == uuid.UUID(submission_id))
            )
            row = existing.scalar_one_or_none()
            if row:
                row.label = result.label
                row.confidence = result.confidence
                row.details = result.details
                row.classifier_version = settings.classifier_version
                row.classified_at = datetime.now(timezone.utc)
            else:
                db.add(Result(
                    submission_id=uuid.UUID(submission_id),
                    classifier_version=settings.classifier_version,
                    label=result.label,
                    confidence=result.confidence,
                    details=result.details,
                ))

            await db.execute(
                update(Submission)
                .where(Submission.id == uuid.UUID(submission_id))
                .values(status="classified", updated_at=datetime.now(timezone.utc))
            )
            await db.commit()

        logger.info("classified", submission_id=submission_id, label=result.label)


async def start_consumer() -> None:
    logger.info("classifier-service starting, connecting to RabbitMQ")
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=5)
        queue = await channel.declare_queue(settings.classification_queue, durable=True)
        logger.info("listening for classification tasks", queue=settings.classification_queue)
        await queue.consume(process_message)
        await asyncio.Future()  # run forever
