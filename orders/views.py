# Use the today_orders view from assessment.py for direct testing
import hashlib
import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from assessment import today_orders

from .models import WebhookEvent
from .services import (
    ClickUpSyncError,
    sync_order_to_clickup,
    verify_woocommerce_signature,
)


@csrf_exempt
@require_POST
def woocommerce_webhook(request):
    signature = request.headers.get("X-WC-Webhook-Signature", "")
    if not verify_woocommerce_signature(request.body, signature):
        return JsonResponse({"error": "Invalid webhook signature"}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    topic = request.headers.get("X-WC-Webhook-Topic", "")
    event_id = request.headers.get("X-WC-Webhook-Delivery-ID")
    if not event_id:
        event_id = hashlib.sha256(request.body).hexdigest()

    event, created = WebhookEvent.objects.get_or_create(
        source="woocommerce",
        event_id=event_id,
        defaults={
            "topic": topic,
            "payload": payload,
            "status": WebhookEvent.STATUS_PENDING,
        },
    )

    if not created and event.status == WebhookEvent.STATUS_PROCESSED:
        return JsonResponse({"ok": True, "status": "duplicate"})

    try:
        sync_record, action = sync_order_to_clickup(payload)
        event.topic = topic
        event.payload = payload
        event.status = WebhookEvent.STATUS_PROCESSED
        event.error_message = ""
        event.processed_at = timezone.now()
        event.save(
            update_fields=[
                "topic",
                "payload",
                "status",
                "error_message",
                "processed_at",
            ]
        )

        return JsonResponse(
            {
                "ok": True,
                "action": action,
                "woo_order_id": sync_record.woo_order_id,
                "clickup_task_id": sync_record.clickup_task_id,
            }
        )
    except ClickUpSyncError as exc:
        event.topic = topic
        event.payload = payload
        event.status = WebhookEvent.STATUS_FAILED
        event.error_message = str(exc)
        event.processed_at = timezone.now()
        event.save(
            update_fields=[
                "topic",
                "payload",
                "status",
                "error_message",
                "processed_at",
            ]
        )
        return JsonResponse({"error": "Failed to sync with ClickUp"}, status=502)
