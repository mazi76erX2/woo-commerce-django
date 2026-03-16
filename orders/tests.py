import base64
import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import OrderSync, WebhookEvent


@override_settings(
    WOO_WEBHOOK_SECRET="test-webhook-secret",
    CLICKUP_TOKEN="test-clickup-token",
    CLICKUP_LIST_ID="123456",
    CLICKUP_API_URL="https://api.clickup.com/api/v2",
)
class WooCommerceWebhookTests(TestCase):
    def _sign_payload(self, payload_bytes):
        digest = hmac.new(
            b"test-webhook-secret", payload_bytes, hashlib.sha256
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _sample_order(self, order_id=101, status="processing"):
        return {
            "id": order_id,
            "status": status,
            "total": "42.00",
            "billing": {
                "first_name": "Jane",
                "last_name": "Doe",
            },
            "line_items": [{"name": "Sample Product"}],
        }

    @patch("orders.services.requests.post")
    def test_creates_clickup_task_for_new_order(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"id": "cu_task_1"}
        mock_post.return_value = mock_response

        payload = self._sample_order(order_id=501)
        raw = json.dumps(payload).encode("utf-8")
        signature = self._sign_payload(raw)

        response = self.client.post(
            reverse("woocommerce-webhook"),
            data=raw,
            content_type="application/json",
            HTTP_X_WC_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WC_WEBHOOK_DELIVERY_ID="evt-501",
            HTTP_X_WC_WEBHOOK_TOPIC="order.created",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(OrderSync.objects.filter(woo_order_id=501).exists())
        sync_record = OrderSync.objects.get(woo_order_id=501)
        self.assertEqual(sync_record.clickup_task_id, "cu_task_1")
        self.assertEqual(sync_record.last_status, "processing")
        self.assertTrue(
            WebhookEvent.objects.filter(event_id="evt-501", status="processed").exists()
        )
        mock_post.assert_called_once()

    @patch("orders.services.requests.put")
    def test_updates_existing_clickup_task(self, mock_put):
        OrderSync.objects.create(
            woo_order_id=777,
            clickup_task_id="cu_existing_777",
            last_status="pending",
            payload_checksum="old",
        )

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"id": "cu_existing_777"}
        mock_put.return_value = mock_response

        payload = self._sample_order(order_id=777, status="completed")
        raw = json.dumps(payload).encode("utf-8")
        signature = self._sign_payload(raw)

        response = self.client.post(
            reverse("woocommerce-webhook"),
            data=raw,
            content_type="application/json",
            HTTP_X_WC_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WC_WEBHOOK_DELIVERY_ID="evt-777",
            HTTP_X_WC_WEBHOOK_TOPIC="order.updated",
        )

        self.assertEqual(response.status_code, 200)
        mock_put.assert_called_once()
        updated = OrderSync.objects.get(woo_order_id=777)
        self.assertEqual(updated.clickup_task_id, "cu_existing_777")
        self.assertEqual(updated.last_status, "completed")

    def test_rejects_invalid_signature(self):
        payload = self._sample_order(order_id=300)
        raw = json.dumps(payload).encode("utf-8")

        response = self.client.post(
            reverse("woocommerce-webhook"),
            data=raw,
            content_type="application/json",
            HTTP_X_WC_WEBHOOK_SIGNATURE="invalid",
            HTTP_X_WC_WEBHOOK_DELIVERY_ID="evt-invalid",
        )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(OrderSync.objects.filter(woo_order_id=300).exists())

    @patch("orders.services.requests.post")
    def test_duplicate_processed_event_does_not_resync(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"id": "cu_task_dup"}
        mock_post.return_value = mock_response

        payload = self._sample_order(order_id=909)
        raw = json.dumps(payload).encode("utf-8")
        signature = self._sign_payload(raw)

        first = self.client.post(
            reverse("woocommerce-webhook"),
            data=raw,
            content_type="application/json",
            HTTP_X_WC_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WC_WEBHOOK_DELIVERY_ID="evt-dup",
        )
        second = self.client.post(
            reverse("woocommerce-webhook"),
            data=raw,
            content_type="application/json",
            HTTP_X_WC_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WC_WEBHOOK_DELIVERY_ID="evt-dup",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(mock_post.call_count, 1)
