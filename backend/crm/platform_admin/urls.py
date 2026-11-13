from django.urls import path

from . import views

urlpatterns = [
    path("platform/companies/", views.companies),
    path(
        "platform/companies/<uuid:organization_id>/owner-invitation/",
        views.reinvite_owner,
    ),
]
