from rest_framework.routers import DefaultRouter

from .views import ProyectoViewSet

router = DefaultRouter()
router.register(r"proyectos", ProyectoViewSet, basename="proyecto")

urlpatterns = router.urls
