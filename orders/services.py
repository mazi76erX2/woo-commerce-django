import logging
from datetime import datetime, time
from django.conf import settings
from django.utils import timezone
from woocommerce import API

logger = logging.getLogger(__name__)


def get_wc_client():
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
