from django.urls import path

from . import views

company = "organizations/<uuid:organization_id>"

urlpatterns = [
    path(f"{company}/pipeline/", views.metadata),
    path(f"{company}/stages/", views.stages),
    path(f"{company}/stages/reorder/", views.reorder_stages),
    path(f"{company}/stages/<uuid:stage_id>/", views.edit_stage),
    path(f"{company}/stages/<uuid:stage_id>/archive/", views.archive_stage),
    path(f"{company}/stages/<uuid:stage_id>/restore/", views.restore_stage),
    path(f"{company}/clients/", views.clients),
    path(f"{company}/clients/<uuid:client_id>/", views.client_detail),
    path(f"{company}/clients/<uuid:client_id>/contacts/", views.add_contact),
    path(f"{company}/leads/", views.leads),
    path(f"{company}/leads/<uuid:lead_id>/", views.lead_detail),
    path(f"{company}/leads/<uuid:lead_id>/comments/", views.comment),
]
