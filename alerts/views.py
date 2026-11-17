from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import EsJefe

from . import services


class AlertasView(APIView):
    """Lista completa de alertas de la empresa del jefe (solo lectura)."""

    permission_classes = [EsJefe]

    def get(self, request):
        alertas = services.generar(request.user.empresa)
        return Response(
            {
                "generado_en": timezone.now(),
                **services.resumen(alertas),
                "alertas": alertas,
            }
        )


class ResumenAlertasView(APIView):
    """Solo los conteos, para el indicador del navbar (consulta liviana)."""

    permission_classes = [EsJefe]

    def get(self, request):
        return Response(services.resumen(empresa=request.user.empresa))
