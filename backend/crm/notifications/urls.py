from django.urls import path

from . import views

urlpatterns = [
    path("me/notifications/", views.notification_settings),
    path("me/telegram/link/", views.telegram_link_create),
    path("me/telegram/unlink/", views.telegram_unlink),
    path("me/push/subscribe/", views.push_subscribe),
    path("me/push/unsubscribe/", views.push_unsubscribe),
]
