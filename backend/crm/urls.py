from django.urls import path

from . import views
from .integrations import views as integrations
from .sales import views as pipeline
from .work import views as work

urlpatterns = [
    path("organizations/<uuid:organization_id>/centers/", integrations.centers),
    path(
        "organizations/<uuid:organization_id>/destinations/", integrations.destinations
    ),
    path(
        "organizations/<uuid:organization_id>/centers/<uuid:center_id>/",
        integrations.edit_center,
    ),
    path(
        "organizations/<uuid:organization_id>/centers/<uuid:center_id>/verify/",
        integrations.verify_center,
    ),
    path(
        "organizations/<uuid:organization_id>/leads/<uuid:lead_id>/transfers/",
        integrations.transfers,
    ),
    path(
        "organizations/<uuid:organization_id>/transfers/<uuid:transfer_id>/retry/",
        integrations.retry,
    ),
    path("organizations/<uuid:organization_id>/summary/", work.summary),
    path("organizations/<uuid:organization_id>/tasks/", work.tasks),
    path("organizations/<uuid:organization_id>/tasks/<uuid:task_id>/", work.edit_task),
    path(
        "organizations/<uuid:organization_id>/leads/<uuid:lead_id>/tasks/",
        work.add_task,
    ),
    path("organizations/<uuid:organization_id>/contacts-due/", work.contacts_due),
    path("organizations/<uuid:organization_id>/pipeline/", pipeline.metadata),
    path("organizations/<uuid:organization_id>/clients/", pipeline.clients),
    path(
        "organizations/<uuid:organization_id>/clients/<uuid:client_id>/",
        pipeline.client_detail,
    ),
    path(
        "organizations/<uuid:organization_id>/clients/<uuid:client_id>/contacts/",
        pipeline.add_contact,
    ),
    path("organizations/<uuid:organization_id>/leads/", pipeline.leads),
    path(
        "organizations/<uuid:organization_id>/leads/<uuid:lead_id>/",
        pipeline.lead_detail,
    ),
    path(
        "organizations/<uuid:organization_id>/leads/<uuid:lead_id>/comments/",
        pipeline.comment,
    ),
    path("auth/session/", views.session),
    path("auth/register/", views.register),
    path("auth/verify/", views.verify),
    path("auth/login/", views.sign_in),
    path("auth/logout/", views.sign_out),
    path("auth/forgot/", views.forgot_password),
    path("auth/reset/", views.reset_password),
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
