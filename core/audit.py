"""Helpers de control de cambios (auditoria)."""

from .models import CambioRegistro


def _fmt(valor):
    if valor is None:
        return ""
    return str(valor)


def registrar_cambio(
    empresa,
    usuario,
    categoria,
    objeto_tipo,
    objeto_id,
    objeto_label,
    campo,
    valor_anterior,
    valor_nuevo,
):
    """Crea un registro de cambio. No hace nada si el valor no cambio."""
    antes = _fmt(valor_anterior)
    despues = _fmt(valor_nuevo)
    if antes == despues:
        return None
    if empresa is None:
        return None
    return CambioRegistro.objects.create(
        empresa=empresa,
        categoria=categoria,
        objeto_tipo=objeto_tipo,
        objeto_id=objeto_id,
        objeto_label=objeto_label[:120],
        campo=campo,
        valor_anterior=antes[:120],
        valor_nuevo=despues[:120],
        usuario=usuario if (usuario and usuario.is_authenticated) else None,
        usuario_nombre=(getattr(usuario, "username", "") or "")[:150],
    )


class AuditaValoresMixin:
    """Mixin para viewsets de catalogo: registra cambios de valores en update.

    Define:
      campos_auditados = {"campo_modelo": "Etiqueta visible", ...}
    y, si hace falta, sobreescribe audit_objeto()/audit_empresa().
    """

    campos_auditados = {}
    categoria_cambio = CambioRegistro.Categoria.PRECIO

    def audit_objeto(self, instance):
        """Devuelve (objeto_tipo, objeto_label) para el registro."""
        return ("objeto", str(instance))

    def audit_empresa(self, instance):
        return getattr(instance, "empresa", None)

    def perform_update(self, serializer):
        instance = serializer.instance
        antes = {f: getattr(instance, f) for f in self.campos_auditados}
        obj = serializer.save()

        empresa = self.audit_empresa(obj)
        objeto_tipo, objeto_label = self.audit_objeto(obj)
        usuario = getattr(self.request, "user", None)
        for campo, etiqueta in self.campos_auditados.items():
            registrar_cambio(
                empresa=empresa,
                usuario=usuario,
                categoria=self.categoria_cambio,
                objeto_tipo=objeto_tipo,
                objeto_id=obj.pk,
                objeto_label=objeto_label,
                campo=etiqueta,
                valor_anterior=antes.get(campo),
                valor_nuevo=getattr(obj, campo),
            )
