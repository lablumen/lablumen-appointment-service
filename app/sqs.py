"""Best-effort SQS publisher for domain events consumed by notification-service.

Messages match `NotificationEvent` (type, to_email, data) — see
notification-service/app/events.py. Publishing never blocks the request path nor fails a
booking: any error is logged and swallowed (the booking is already persisted).
"""

import asyncio
import json
import logging

import boto3

from .config import settings

logger = logging.getLogger(__name__)
_sqs = boto3.client("sqs", region_name=settings.aws_region)


async def publish_event(event_type: str, to_email: str | None, data: dict) -> None:
    if not settings.notifications_queue_url:
        logger.warning("NOTIFICATIONS_QUEUE_URL unset; skipping %s event", event_type)
        return
    if not to_email:
        logger.warning("No recipient email; skipping %s event", event_type)
        return
    body = json.dumps({"type": event_type, "to_email": to_email, "data": data})
    try:
        await asyncio.to_thread(
            _sqs.send_message,
            QueueUrl=settings.notifications_queue_url,
            MessageBody=body,
        )
    except Exception:
        logger.exception("Failed to publish %s event to SQS", event_type)
