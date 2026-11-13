from django.urls import path

from . import views

company = "organizations/<uuid:organization_id>"

urlpatterns = [
    path(f"{company}/summary/", views.summary),
    path(f"{company}/tasks/", views.tasks),
    path(f"{company}/tasks/<uuid:task_id>/", views.edit_task),
    path(f"{company}/leads/<uuid:lead_id>/tasks/", views.add_task),
    path(f"{company}/contacts-due/", views.contacts_due),
]
