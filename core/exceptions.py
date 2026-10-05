from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Convierte errores de integridad de la BD (p. ej. unique_together) en una
    respuesta 400 legible, en vez de un 500."""
    response = exception_handler(exc, context)
    if response is None and isinstance(exc, IntegrityError):
        return Response(
            {
                "detail": (
                    "No se pudo guardar: el registro ya existe o viola una "
                    "restriccion de unicidad (revisa codigos/colores duplicados)."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return response
