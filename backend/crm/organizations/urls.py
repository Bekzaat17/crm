from django.urls import path

from . import views

urlpatterns = [
    path("invitations/preview/", views.invitation_preview),
    path("invitations/accept/", views.accept_invitation),
    path("organizations/<uuid:organization_id>/", views.organization),
    path("organizations/<uuid:organization_id>/team/", views.team),
    path("organizations/<uuid:organization_id>/audit/", views.audit),
    path("organizations/<uuid:organization_id>/invitations/", views.create_invitation),
    path(
        "organizations/<uuid:organization_id>/invitations/<uuid:invitation_id>/revoke/",
        views.revoke_invitation,
    ),
    path(
        "organizations/<uuid:organization_id>/members/<uuid:membership_id>/deactivate/",
        views.deactivate_member,
    ),
]
