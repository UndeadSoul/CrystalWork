from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Formato comun de errores de la API:

      - Errores de campo: {"campo": ["mensaje"], ...}  (formato DRF).
      - Error general:    {"detail": "mensaje"}.

    Ademas convierte en 400 legibles los errores que DRF no maneja: los de
    integridad de la BD (p. ej. unique_together o CHECK) y los ValidationError
    de Django (validaciones de modelo).
    """
    if isinstance(exc, DjangoValidationError):
        data = (
            exc.message_dict
            if hasattr(exc, "error_dict")
            else {"detail": " ".join(exc.messages)}
        )
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    response = exception_handler(exc, context)
    if response is None and isinstance(exc, IntegrityError):
        return Response(
            {
                "detail": (
                    "No se pudo guardar: el registro ya existe o tiene valores "
                    "fuera de rango."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ValidationError("texto") lanzado desde una vista llega como lista:
    # se normaliza a {"detail": "..."}.
    if response is not None and isinstance(response.data, list):
        response.data = {"detail": " ".join(str(m) for m in response.data)}
    return response
