from django.db import models


class OrderSync(models.Model):
    woo_order_id = models.PositiveBigIntegerField(unique=True)
    clickup_task_id = models.CharField(max_length=64, blank=True)
    last_status = models.CharField(max_length=32, default="unknown")
    payload_checksum = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_synced_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.woo_order_id} -> {self.clickup_task_id or 'pending'}"


class WebhookEvent(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
    ]

    source = models.CharField(max_length=32, default="woocommerce")
    event_id = models.CharField(max_length=128)
    topic = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    payload = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "event_id"], name="unique_webhook_source_event"
            )
        ]

    def __str__(self):
        return f"{self.source}:{self.event_id} ({self.status})"
