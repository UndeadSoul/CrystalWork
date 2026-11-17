from django.urls import path

from .views import AlertasView, ResumenAlertasView

urlpatterns = [
    path("alertas/", AlertasView.as_view(), name="alertas"),
    path("alertas/resumen/", ResumenAlertasView.as_view(), name="alertas-resumen"),
]
