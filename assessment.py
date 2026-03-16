from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import login_required
import requests
import logging

logger = logging.getLogger(__name__)


@login_required
def today_orders(request):
    # 1. Calculate 'Today' dynamically (Midnight in local timezone)
    today_start = timezone.localtime().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    iso_date = today_start.isoformat()

    try:
        # 2. Call WC API with pagination and timeout
        response = requests.get(
            f"{settings.WOO_API_URL}/orders",
            params={"after": iso_date, "per_page": 100},
            auth=(settings.WOO_KEY, settings.WOO_SECRET),
            timeout=10,
        )
        response.raise_for_status()
        orders = response.json()

        # 3. Shape response data safely
        results = []
        for o in orders:
            billing = o.get("billing", {})
            results.append(
                {
                    "id": o.get("id"),
                    "customer": f"{billing.get('first_name', 'Guest')} {billing.get('last_name', '')}".strip(),
                    "total": o.get("total"),
                    "status": o.get("status"),
                    "url": f"/orders/{o.get('id')}/",
                }
            )
        return JsonResponse(results, safe=False)

    except requests.exceptions.RequestException as e:
        logger.error(f"WooCommerce API Failure: {str(e)}")
        return JsonResponse({"error": "Unable to fetch orders"}, status=502)
