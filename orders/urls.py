from django.urls import path
from . import views

urlpatterns = [
    path("today/", views.today_orders, name="today-orders"),
]
