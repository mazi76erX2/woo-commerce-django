import logging
import hashlib
import hmac
import base64
import json
from datetime import datetime, time
from django.conf import settings
from django.utils import timezone
import requests

from .models import OrderSync

logger = logging.getLogger(__name__)


class ClickUpSyncError(Exception):
    pass


def get_wc_client():
    from woocommerce import API

    return API(
        url=settings.WOO_API_URL,
        consumer_key=settings.WOO_CONSUMER_KEY,
        consumer_secret=settings.WOO_CONSUMER_SECRET,
        version="wc/v3",
        timeout=10,
    )


def get_today_orders():
    wcapi = get_wc_client()
    now = timezone.now()

    today_start = timezone.make_aware(
        datetime.combine(now.date(), time.min)
    ).isoformat()

    today_end = timezone.make_aware(datetime.combine(now.date(), time.max)).isoformat()

    all_orders = []
    page = 1

    while True:
        response = wcapi.get(
            "orders",
            params={
                "after": today_start,
                "before": today_end,
                "per_page": 100,
                "page": page,
            },
        )

        if response.status_code != 200:
            raise Exception(f"WC API error: {response.status_code}")

        orders = response.json()
        if not orders:
            break

        all_orders.extend(orders)

        total_pages = int(response.headers.get("X-WP-TotalPages", 1))
        if page >= total_pages:
            break
        page += 1

    return all_orders


def format_order(order):
    billing = order.get("billing", {})
    first = billing.get("first_name", "")
    last = billing.get("last_name", "")
    name = f"{first} {last}".strip() or "Guest Customer"

    return {
        "id": order["id"],
        "customer": name,
        "total": order.get("total", "0.00"),
        "status": order.get("status", "unknown"),
        "date_created": order.get("date_created", ""),
    }


def verify_woocommerce_signature(payload_bytes, signature_header):
    secret = getattr(settings, "WOO_WEBHOOK_SECRET", "")
    if not secret or not signature_header:
        return False

    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    expected_signature = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature_header)


def _build_order_checksum(order_data):
    raw = json.dumps(order_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clickup_headers():
    token = getattr(settings, "CLICKUP_TOKEN", "")
    if not token:
        raise ClickUpSyncError("CLICKUP_TOKEN is not configured")
    return {
        "Authorization": token,
        "Content-Type": "application/json",
    }


def _build_clickup_payload(order_data):
    billing = order_data.get("billing", {})
    first_name = billing.get("first_name", "")
    last_name = billing.get("last_name", "")
    customer = f"{first_name} {last_name}".strip() or "Guest"
    order_id = order_data.get("id")
    line_items = order_data.get("line_items", [])
    item_summary = ", ".join(item.get("name", "Item") for item in line_items[:5])

    description_lines = [
        f"WooCommerce Order: #{order_id}",
        f"Customer: {customer}",
        f"Status: {order_data.get('status', 'unknown')}",
        f"Total: {order_data.get('total', '0.00')}",
    ]
    if item_summary:
        description_lines.append(f"Items: {item_summary}")

    return {
        "name": f"Order #{order_id} - {customer}",
        "description": "\n".join(description_lines),
        "status": "to do",
    }


def sync_order_to_clickup(order_data):
    woo_order_id = order_data.get("id")
    if not woo_order_id:
        raise ClickUpSyncError("WooCommerce order payload missing 'id'")

    clickup_api_url = getattr(
        settings, "CLICKUP_API_URL", "https://api.clickup.com/api/v2"
    )
    clickup_list_id = getattr(settings, "CLICKUP_LIST_ID", "")
    if not clickup_list_id:
        raise ClickUpSyncError("CLICKUP_LIST_ID is not configured")

    checksum = _build_order_checksum(order_data)
    payload = _build_clickup_payload(order_data)

    sync_record, _ = OrderSync.objects.get_or_create(
        woo_order_id=woo_order_id,
        defaults={
            "last_status": order_data.get("status", "unknown"),
            "payload_checksum": checksum,
        },
    )

    if sync_record.clickup_task_id and sync_record.payload_checksum == checksum:
        return sync_record, "unchanged"

    headers = _clickup_headers()

    try:
        if sync_record.clickup_task_id:
            response = requests.put(
                f"{clickup_api_url}/task/{sync_record.clickup_task_id}",
                json=payload,
                headers=headers,
                timeout=10,
            )
            action = "updated"
        else:
            response = requests.post(
                f"{clickup_api_url}/list/{clickup_list_id}/task",
                json=payload,
                headers=headers,
                timeout=10,
            )
            action = "created"

        response.raise_for_status()
        body = response.json()
    except requests.RequestException as exc:
        raise ClickUpSyncError(f"ClickUp request failed: {exc}") from exc
    except ValueError as exc:
        raise ClickUpSyncError("ClickUp response is not valid JSON") from exc

    if action == "created":
        clickup_task_id = body.get("id", "")
        if not clickup_task_id:
            raise ClickUpSyncError("ClickUp create task response missing 'id'")
        sync_record.clickup_task_id = clickup_task_id

    sync_record.last_status = order_data.get("status", "unknown")
    sync_record.payload_checksum = checksum
    sync_record.save(
        update_fields=[
            "clickup_task_id",
            "last_status",
            "payload_checksum",
            "last_synced_at",
        ]
    )

    return sync_record, action
