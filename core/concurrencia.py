"""Control de concurrencia optimista.

Problema: dos usuarios trabajan sobre el mismo registro con datos que cargaron
en momentos distintos; el ultimo en guardar pisaba al otro sin aviso (o, en
cotizaciones, se aprobaba una version que el aprobador nunca vio).

Solucion: cada registro tiene un numero de `version`. Cada cambio exige la
version que el usuario tenia en pantalla y la "toma" con un UPDATE condicional
atomico (tomar_version). Si otro usuario lo cambio entre medio, el UPDATE no
afecta filas y se responde 409 con lo que paso. Al ser una sola sentencia no
hay ventana entre revisar y escribir (funciona igual en SQLite y Postgres).
Debe ejecutarse dentro de una transaccion junto con el resto del cambio, para
que un error lo deshaga todo.

Se usa en:
  - Cotizaciones: editar, aprobar, rechazar, recalcular (tomar_cotizacion).
  - Catalogo de precios: edicion de cada fila (ControlVersionMixin).
"""

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from .models import CambioRegistro, Cotizacion
from .zona import formatear_fecha_hora


class Conflicto(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflicto_version"

    def __init__(self, mensaje, actual=None):
        # "code" para que el frontend lo reconozca; "actual": el registro tal
        # como quedo, para mostrar su valor vigente.
        detalle = {"detail": mensaje, "code": self.default_code}
        if actual is not None:
            detalle["actual"] = actual
        super().__init__(detalle)


def version_esperada(request):
    """Version del registro que el usuario tenia en pantalla."""
    try:
        return int(request.data.get("version"))
    except (TypeError, ValueError):
        raise ValidationError(
            {"version": "Falta la versión del registro. Recarga la página."}
        )


def tomar_version(instancia, version, campo="version", condiciones=None, **cambios):
    """UPDATE condicional atomico: solo si el registro sigue en `version` (y
    cumple `condiciones`). Incrementa la version y aplica `cambios` en la misma
    sentencia. Refresca `instancia`. Devuelve False si otro usuario lo cambio."""
    filtro = {"pk": instancia.pk, campo: version, **(condiciones or {})}
    filas = type(instancia).objects.filter(**filtro).update(
        **{campo: F(campo) + 1}, **cambios
    )
    instancia.refresh_from_db()
    return bool(filas)


# Hora en la zona del usuario: coincide con la que ve en pantalla (core/zona.py).
_cuando = formatear_fecha_hora


# ------------------------------------------------------------------
# Cotizaciones
# ------------------------------------------------------------------


def mensaje_conflicto(cotizacion):
    if cotizacion.estado != Cotizacion.Estado.PENDIENTE:
        quien = cotizacion.resuelta_por.username if cotizacion.resuelta_por else "otro usuario"
        return (
            f"La cotización ya fue {cotizacion.get_estado_display().lower()} por "
            f"{quien} ({_cuando(cotizacion.fecha_resolucion)})."
        )
    quien = cotizacion.modificada_por.username if cotizacion.modificada_por else "otro usuario"
    return (
        f"La cotización fue modificada por {quien} ({_cuando(cotizacion.modificada_en)}) "
        "después de que la abriste. Revisa la versión actual antes de continuar."
    )


def tomar_cotizacion(cotizacion, version, usuario, **cambios):
    """Toma la cotizacion para modificarla: solo si sigue pendiente y en la
    version esperada. Registra quien la modifico y aplica `cambios` (p. ej.
    estado al aprobar) en la misma sentencia. Lanza Conflicto si otro usuario
    la cambio."""
    ok = tomar_version(
        cotizacion,
        version,
        condiciones={"estado": Cotizacion.Estado.PENDIENTE},
        modificada_por=usuario,
        modificada_en=timezone.now(),
        **cambios,
    )
    if not ok:
        raise Conflicto(mensaje_conflicto(cotizacion))
    return cotizacion


# ------------------------------------------------------------------
# Catalogo de precios
# ------------------------------------------------------------------


class ControlVersionMixin:
    """Para viewsets del catalogo (junto con AuditaValoresMixin): la edicion
    exige la version de la fila que el usuario tenia en pantalla. Si otro
    usuario la cambio, responde 409 con quien/cuando (del registro de cambios)
    y la fila actual."""

    campo_version = "version"

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        if not tomar_version(obj, version_esperada(request), self.campo_version):
            raise Conflicto(
                self._mensaje_conflicto(obj), actual=self.get_serializer(obj).data
            )
        return super().update(request, *args, **kwargs)

    def _mensaje_conflicto(self, obj):
        objeto_tipo, _ = self.audit_objeto(obj)
        ultimo = (
            CambioRegistro.objects.filter(objeto_tipo=objeto_tipo, objeto_id=obj.pk)
            .order_by("-creado_en")
            .first()
        )
        if ultimo:
            return (
                f"{ultimo.usuario_nombre or 'Otro usuario'} modificó este valor "
                f"({_cuando(ultimo.creado_en)}) mientras editabas."
            )
        return "Otro usuario modificó este valor mientras editabas."
