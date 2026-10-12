from django.urls import path

from .views import IngresosView, ResumenView

urlpatterns = [
    path("analytics/resumen/", ResumenView.as_view(), name="analytics-resumen"),
    path("analytics/ingresos/", IngresosView.as_view(), name="analytics-ingresos"),
]
