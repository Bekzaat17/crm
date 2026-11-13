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
    path("extension/authorize/", views.authorize_extension),
    path("ext/session/", views.ext_session),
    path("ext/session/revoke/", views.ext_revoke),
    path("ext/conversations/lookup/", views.ext_lookup),
    path("ext/conversations/track/", views.ext_track),
    path("ext/conversations/untrack/", views.ext_untrack),
    path("ext/match/", views.ext_match),
    path("ext/leads/", views.ext_leads),
    path("ext/imports/", views.ext_import),
]
