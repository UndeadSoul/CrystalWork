from rest_framework.routers import DefaultRouter

from .views import EmpresaViewSet, UsuarioViewSet

router = DefaultRouter()
router.register(r"usuarios", UsuarioViewSet, basename="usuario")
router.register(r"empresas", EmpresaViewSet, basename="empresa")

urlpatterns = router.urls
