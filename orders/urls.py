from django.urls import path
from . import views

urlpatterns = [
    path("today/", views.today_orders, name="today-orders"),
    path("webhook/woocommerce/", views.woocommerce_webhook, name="woocommerce-webhook"),
]
