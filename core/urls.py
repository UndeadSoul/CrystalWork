from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ClienteViewSet,
    CotizacionViewSet,
    EmpresaConfigView,
    InsumoViewSet,
    OpcionesCotizacionView,
    PerfilIndividualViewSet,
    PerfilSerieViewSet,
    PlanchaVidrioViewSet,
    PrecioPerfilIndividualViewSet,
    PrecioSerieViewSet,
    SerieAluminioViewSet,
)

router = DefaultRouter()
router.register(r"clientes", ClienteViewSet, basename="cliente")
router.register(r"cotizaciones", CotizacionViewSet, basename="cotizacion")

# Catalogo de precios
router.register(r"catalogo/series", SerieAluminioViewSet, basename="serie")
router.register(r"catalogo/perfiles-serie", PerfilSerieViewSet, basename="perfil-serie")
router.register(r"catalogo/precios-serie", PrecioSerieViewSet, basename="precio-serie")
router.register(
    r"catalogo/perfiles-individuales",
    PerfilIndividualViewSet,
    basename="perfil-individual",
)
router.register(
    r"catalogo/precios-perfil-individual",
    PrecioPerfilIndividualViewSet,
    basename="precio-perfil-individual",
)
router.register(r"catalogo/planchas", PlanchaVidrioViewSet, basename="plancha")
router.register(r"catalogo/insumos", InsumoViewSet, basename="insumo")

urlpatterns = [
    path(
        "cotizaciones/opciones/",
        OpcionesCotizacionView.as_view(),
        name="cotizacion-opciones",
    ),
    path("catalogo/empresa/", EmpresaConfigView.as_view(), name="empresa-config"),
    *router.urls,
]
