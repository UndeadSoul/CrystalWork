from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

from users.views import TokenEmpresaActivaView


urlpatterns = [
    path("admin/", admin.site.urls),

    # Autenticacion (JWT)
    path("api/token/", TokenEmpresaActivaView.as_view(), name="get_token"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("api-auth/", include("rest_framework.urls")),

    # Dominio
    path("api/", include("api.urls")),
    path("api/", include("users.urls")),
    path("api/", include("core.urls")),
    path("api/", include("projects.urls")),
    path("api/", include("analytics.urls")),
]
