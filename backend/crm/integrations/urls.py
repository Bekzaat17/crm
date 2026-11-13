from django.urls import path

from . import views

company = "organizations/<uuid:organization_id>"

urlpatterns = [
    path(f"{company}/centers/", views.centers),
    path(f"{company}/destinations/", views.destinations),
    path(f"{company}/centers/<uuid:center_id>/", views.edit_center),
    path(f"{company}/centers/<uuid:center_id>/verify/", views.verify_center),
    path(f"{company}/leads/<uuid:lead_id>/transfers/", views.transfers),
    path(f"{company}/transfers/<uuid:transfer_id>/retry/", views.retry),
]
