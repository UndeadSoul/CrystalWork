from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ClienteViewSet, CotizacionViewSet, OpcionesCotizacionView

router = DefaultRouter()
router.register(r"clientes", ClienteViewSet, basename="cliente")
router.register(r"cotizaciones", CotizacionViewSet, basename="cotizacion")

urlpatterns = [
    path("cotizaciones/opciones/", OpcionesCotizacionView.as_view(), name="cotizacion-opciones"),
    *router.urls,
]
