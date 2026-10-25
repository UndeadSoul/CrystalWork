"""Permisos de la API.

Los datos operativos (clientes, cotizaciones, proyectos, precios, dashboard)
son privados de cada empresa: solo los ven sus usuarios. El administrador del
sistema (superusuario, sin empresa) NO accede a ellos; solo gestiona empresas
y usuarios (users/views.py).

EsUsuarioDeEmpresa es el permiso por defecto de DRF (settings), asi que un
endpoint nuevo queda cerrado al administrador salvo que se abra a proposito.
"""

from rest_framework.permissions import BasePermission


class EsUsuarioDeEmpresa(BasePermission):
    """Usuario autenticado que pertenece a una empresa (jefe u operario)."""

    message = "Esta sección es solo para usuarios de una empresa."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and not user.is_superuser
            and user.empresa_id is not None
        )


class EsJefe(EsUsuarioDeEmpresa):
    """Jefe de una empresa (precios, finanzas, aprobar cotizaciones)."""

    message = "Solo el jefe de la empresa puede realizar esta acción."

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.es_jefe
