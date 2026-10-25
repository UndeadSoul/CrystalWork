"""Crea datos base para dejar el sistema usable en una máquina nueva.

Idempotente y NO destructivo: crea lo que falta y rellena solo los valores
vacíos (no pisa precios/pesos que el jefe ya haya editado). Pensado para
bootstrap tras `migrate` cuando la base de datos viene vacía.

    python manage.py seed_demo

Crea: empresa demo, usuarios (admin del sistema, jefe, operario) y el catálogo
completo con precios y planchas de vidrio (sin esto no se pueden cotizar
ventanas, porque el formulario exige un vidrio con plancha).
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.catalog import asegurar_catalogo
from core.models import (
    ColorAluminio,
    Insumo,
    PlanchaVidrio,
    PrecioSerie,
    SerieAluminio,
    TipoVidrio,
)
from users.models import Empresa

Usuario = get_user_model()

EMPRESA_NOMBRE = "Ventanas Demo"

# Usuarios: (username, password, rol o None=admin del sistema).
USUARIOS = [
    ("admin", "admin12345", None),
    ("jefe", "jefe12345", Usuario.Rol.JEFE),
    ("operario", "operario12345", Usuario.Rol.OPERARIO),
]

# Peso del paquete (kg) por serie, usado como denominador del costo de aluminio.
PESO_SERIE = {"L20": Decimal("7.000"), "L25": Decimal("7.500")}

# Peso de tira (kg) por perfil (cualquier valor > 0 permite calcular precio).
PESO_PERFIL = Decimal("0.900")

# Precio del paquete por color (CLP), por serie.
PRECIO_SERIE = {
    "L20": 48000,
    "L25": 56000,
}

# Planchas de vidrio: precio del paquete por tipo (ancho/alto en m).
PRECIO_VIDRIO = {
    "BRONCE_4": 51000,
    "BRONCE_5": 60000,
    "INCOLORO_4": 46000,
    "INCOLORO_5": 54000,
    "SOLARCOOL_4": 72000,
    "SOLARCOOL_5": 83000,
}

# Insumos: (precio_paquete, cantidad_paquete).
INSUMOS = {
    "FELPA": (3000, Decimal("100")),
    "BURLETE": (5200, Decimal("100")),
    "PESTILLO_L20": (1500, Decimal("1")),
    "PESTILLO_L25": (1500, Decimal("1")),
    "CARACOL": (2000, Decimal("1")),
    "RODAMIENTO_L20": (800, Decimal("1")),
    "RODAMIENTO_L25": (800, Decimal("1")),
    "TORNILLO": (50, Decimal("1")),
    "SILICONA": (3500, Decimal("1")),
}


class Command(BaseCommand):
    help = "Crea empresa demo, usuarios y catálogo con precios (idempotente)."

    @transaction.atomic
    def handle(self, *args, **options):
        empresa, creada = Empresa.objects.get_or_create(
            nombre=EMPRESA_NOMBRE,
            defaults={
                "rut": "76.000.000-0",
                "margen_ganancia_pct": Decimal("30.00"),
                "precio_transporte_km": 1500,
            },
        )
        self.stdout.write(
            f"Empresa: {empresa.nombre} ({'creada' if creada else 'ya existía'})"
        )

        self._usuarios(empresa)
        self._catalogo(empresa)

        self.stdout.write(self.style.SUCCESS("\nSeed completo. Puedes iniciar sesión con:"))
        for username, password, rol in USUARIOS:
            etiqueta = "admin del sistema" if rol is None else rol
            self.stdout.write(f"  {username} / {password}  ({etiqueta})")

    # ------------------------------------------------------------------
    def _usuarios(self, empresa):
        for username, password, rol in USUARIOS:
            user, creado = Usuario.objects.get_or_create(username=username)
            if creado:
                user.set_password(password)
                if rol is None:
                    user.is_staff = True
                    user.is_superuser = True
                    user.empresa = None
                    user.rol = None
                else:
                    user.empresa = empresa
                    user.rol = rol
                user.save()
                self.stdout.write(f"  Usuario creado: {username}")
            else:
                self.stdout.write(f"  Usuario ya existía: {username} (sin cambios)")

    # ------------------------------------------------------------------
    def _catalogo(self, empresa):
        # Esqueleto fijo (series, perfiles, insumos).
        asegurar_catalogo(empresa)

        for serie in SerieAluminio.objects.filter(empresa=empresa):
            # Peso del paquete: solo si está vacío.
            if not serie.peso_total_kg:
                serie.peso_total_kg = PESO_SERIE.get(serie.codigo, Decimal("7.000"))
                serie.save(update_fields=["peso_total_kg"])

            # Peso de cada perfil: solo si está en 0.
            for perfil in serie.perfiles.all():
                if not perfil.peso_kg:
                    perfil.peso_kg = PESO_PERFIL
                    perfil.save(update_fields=["peso_kg"])

            # Precio del paquete por color (crea los que falten).
            for color, _label in ColorAluminio.choices:
                PrecioSerie.objects.get_or_create(
                    serie=serie,
                    color=color,
                    defaults={"precio": PRECIO_SERIE.get(serie.codigo, 50000)},
                )

        # Planchas de vidrio (sin esto no se puede cotizar).
        for tipo, _label in TipoVidrio.choices:
            PlanchaVidrio.objects.get_or_create(
                empresa=empresa,
                tipo_vidrio=tipo,
                defaults={
                    "ancho_plancha_m": Decimal("2.400"),
                    "alto_plancha_m": Decimal("3.600"),
                    "precio": PRECIO_VIDRIO.get(tipo, 50000),
                },
            )

        # Valores de insumos: solo si están vacíos.
        for codigo, (precio, cantidad) in INSUMOS.items():
            ins = Insumo.objects.filter(empresa=empresa, codigo=codigo).first()
            if ins and not ins.precio_paquete:
                ins.precio_paquete = precio
                ins.cantidad_paquete = cantidad
                ins.save(update_fields=["precio_paquete", "cantidad_paquete"])

        self.stdout.write("  Catálogo asegurado (series, precios, planchas, insumos).")
