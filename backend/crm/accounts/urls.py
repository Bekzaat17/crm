from django.urls import path

from . import views

urlpatterns = [
    path("auth/session/", views.session),
    path("auth/login/", views.sign_in),
    path("auth/logout/", views.sign_out),
    path("auth/forgot/", views.forgot_password),
    path("auth/reset/", views.reset_password),
]
