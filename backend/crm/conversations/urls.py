from django.urls import path

from . import views

company = "organizations/<uuid:organization_id>"

urlpatterns = [
    path(f"{company}/extension-tokens/", views.extension_tokens),
    path(
        f"{company}/extension-tokens/<uuid:token_id>/revoke/",
        views.revoke_extension_token,
    ),
    path(f"{company}/leads/<uuid:lead_id>/conversations/", views.conversations),
    path("ext/session/", views.ext_session),
    path("ext/leads/", views.ext_leads),
    path("ext/imports/", views.ext_import),
]
