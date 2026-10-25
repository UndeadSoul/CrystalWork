"""Deja vacio el RUT de las empresas que no pasa la validacion (modulo 11).

Las empresas existentes se crearon antes de validar su RUT (users.0004) y con
un RUT invalido no se podian editar desde la pantalla de Empresas. El RUT de
empresa es opcional, asi que se limpia (no se conoce el real). La validacion
se copia aqui a proposito (ver core.0011).
"""

from django.db import migrations


def _rut_valido(rut):
    limpio = (rut or "").replace(".", "").replace("-", "").strip().upper()
    if not 2 <= len(limpio) <= 9 or not limpio[:-1].isdigit():
        return False
    suma, mult = 0, 2
    for d in reversed(limpio[:-1]):
        suma += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    resto = 11 - (suma % 11)
    return {11: "0", 10: "K"}.get(resto, str(resto)) == limpio[-1]


def sanear(apps, schema_editor):
    Empresa = apps.get_model("users", "Empresa")
    for e in Empresa.objects.exclude(rut=""):
        if not _rut_valido(e.rut):
            e.rut = ""
            e.save(update_fields=["rut"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_version_catalogo"),
    ]

    operations = [
        migrations.RunPython(sanear, migrations.RunPython.noop),
    ]
