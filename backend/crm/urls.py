from django.urls import include, path

# Маршруты доменов; URL API не зависят от порядка: path() сопоставляет путь целиком.
urlpatterns = [
    path("", include("crm.integrations.urls")),
    path("", include("crm.work.urls")),
    path("", include("crm.sales.urls")),
    path("", include("crm.accounts.urls")),
    path("", include("crm.organizations.urls")),
    path("", include("crm.notifications.urls")),
    path("", include("crm.conversations.urls")),
]
