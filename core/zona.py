"""Zona horaria del usuario para los textos con hora que arma el servidor.

Las fechas se guardan en UTC y las reglas de negocio (fecha de hoy para un
pago, agrupacion por dia/mes del dashboard) usan la zona del servidor
(settings.TIME_ZONE). Pero los mensajes con hora (p. ej. "modificada por
jefe2 (24-10-2026 16:05)") deben coincidir con lo que el usuario ve en
pantalla, que el frontend muestra en la zona de su computador.

El frontend envia su zona en la cabecera X-Zona-Horaria; este middleware la
guarda en una variable de contexto (no activa la zona de Django, para no
alterar las reglas de negocio) y `formatear_fecha_hora` la usa.
"""

from contextvars import ContextVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

CABECERA = "HTTP_X_ZONA_HORARIA"

_zona_cliente = ContextVar("zona_cliente", default=None)


def _zona_valida(nombre):
    if not nombre or len(nombre) > 64:
        return None
    try:
        return ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError):
        return None


class ZonaClienteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _zona_cliente.set(_zona_valida(request.META.get(CABECERA)))
        try:
            return self.get_response(request)
        finally:
            _zona_cliente.reset(token)


def formatear_fecha_hora(fecha):
    """"24-10-2026 16:05" en la zona del usuario (o la del servidor si el
    navegador no la informo)."""
    if not fecha:
        return ""
    zona = _zona_cliente.get() or timezone.get_current_timezone()
    return timezone.localtime(fecha, zona).strftime("%d-%m-%Y %H:%M")
