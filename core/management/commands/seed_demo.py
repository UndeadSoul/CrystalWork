"""Poblado de la base de datos para una máquina nueva o para demostración.

    python manage.py seed_demo              # mínimo (verificar que funciona)
    python manage.py seed_demo --extenso    # población grande (demo/dashboard)
    python manage.py seed_demo --reset       # borra datos de prueba y recrea
    python manage.py seed_demo --reset --extenso

Siempre crea: admin del sistema, empresa "Aluminios Las Vegas", su jefe y
operario, y el catálogo poblado con valores de referencia (pesos, tamaños y
precios de aluminio, vidrio y agregados), para poder cotizar de inmediato. La
config de la empresa usa los defaults del modelo (margen 100%, transporte
$1.000/km, mermas 20/20, alertas 3/14/7).

  - mínimo: 2 clientes con 2 proyectos cada uno.
  - --extenso: 10 clientes, 4 cotizaciones pendientes, ~65 proyectos entregados
    y pagados (de hace 2 a 12 meses) y ~15 recientes con estados variados.

Las ventanas de cada cotización se generan al azar (tipo, medidas, color y
vidrio) dentro de rangos realistas; los precios los calcula el motor.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.catalog import PRECIO_VIDRIO_DEFECTO, poblar_catalogo_defecto
from core.models import (
    CambioRegistro,
    Cliente,
    ColorAluminio,
    Cotizacion,
    VentanaCotizada,
)
from core.pricing import desglose_iva, recalcular_cotizacion
from projects.models import Pago, Proyecto
from users.models import Empresa

Usuario = get_user_model()

EMPRESA_NOMBRE = "Aluminios Las Vegas"
EMPRESA_RUT = "76.000.000-0"

# (username, password, rol o None=admin del sistema).
USUARIOS = [
    ("admin", "admin12345", None),
    ("jefe", "jefe12345", Usuario.Rol.JEFE),
    ("operario", "operario12345", Usuario.Rol.OPERARIO),
]

# Solo correderas (los tipos con serie y precio definidos).
TIPOS = ["Linea20simple", "Linea20lluvia", "Linea25simple", "Linea25lluvia"]
COLORES = [c for c, _ in ColorAluminio.choices]
# Solo los tipos de vidrio con plancha definida (los que crea poblar_catalogo).
VIDRIOS = list(PRECIO_VIDRIO_DEFECTO)

# Clientes de demostración (los 2 primeros se usan en el modo mínimo).
CLIENTES = [
    ("Juan Pérez Soto", "+56 9 8111 2201", "Av. Los Leones 1234, Providencia"),
    ("María González Rojas", "+56 9 8111 2202", "Pasaje Las Rosas 45, Maipú"),
    ("Pedro Araya Muñoz", "+56 9 8111 2203", "Camino El Alba 980, Las Condes"),
    ("Carla Fuentes Díaz", "+56 9 8111 2204", "Gran Avenida 5521, San Miguel"),
    ("Jorge Sepúlveda Lara", "+56 9 8111 2205", "O'Higgins 230, Rancagua"),
    ("Ana Morales Vega", "+56 9 8111 2206", "Freire 112, Temuco"),
    ("Luis Cáceres Pino", "+56 9 8111 2207", "Prat 876, Concepción"),
    ("Daniela Reyes Núñez", "+56 9 8111 2208", "Colón 450, Antofagasta"),
    ("Rodrigo Tapia Silva", "+56 9 8111 2209", "Balmaceda 67, La Serena"),
    ("Paula Herrera Campos", "+56 9 8111 2210", "Arturo Prat 1500, Valparaíso"),
]


def _rut(num):
    """Formatea un RUT con dígito verificador válido: 12345678 -> 12.345.678-5."""
    rev = [int(d) for d in reversed(str(num))]
    factores = [2, 3, 4, 5, 6, 7]
    s = sum(d * factores[i % 6] for i, d in enumerate(rev))
    r = 11 - (s % 11)
    dv = {11: "0", 10: "K"}.get(r, str(r))
    return f"{num:,}".replace(",", ".") + f"-{dv}"


class Command(BaseCommand):
    help = "Puebla la base (mínimo o --extenso). --reset borra y recrea."

    def add_arguments(self, parser):
        parser.add_argument(
            "--extenso",
            action="store_true",
            help="Población grande para demostración (10 clientes, ~80 proyectos).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra TODOS los datos de prueba antes de poblar.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(2026)  # reproducible (respaldo estable)

        if options["reset"]:
            self._reset()

        empresa = self._empresa()
        jefe = self._usuarios(empresa)
        poblar_catalogo_defecto(empresa)
        self.stdout.write("  Catálogo poblado con valores de referencia.")

        if options["extenso"]:
            self._poblar_extenso(empresa, jefe)
        else:
            self._poblar_minimo(empresa, jefe)

        self.stdout.write(self.style.SUCCESS("\nSeed completo. Inicia sesión con:"))
        for username, password, rol in USUARIOS:
            etiqueta = "admin del sistema" if rol is None else rol
            self.stdout.write(f"  {username} / {password}  ({etiqueta})")

    # ------------------------------------------------------------------ reset
    def _reset(self):
        # Orden por las FK PROTECT (pagos -> proyectos -> cotizaciones ->
        # clientes -> auditoría -> usuarios -> empresas, que cascada el catálogo).
        Pago.objects.all().delete()
        Proyecto.objects.all().delete()
        Cotizacion.objects.all().delete()  # cascada VentanaCotizada
        Cliente.objects.all().delete()
        CambioRegistro.objects.all().delete()
        Usuario.objects.all().delete()
        Empresa.objects.all().delete()  # cascada series/perfiles/precios/planchas/insumos
        self.stdout.write(self.style.WARNING("  --reset: datos de prueba borrados."))

    # --------------------------------------------------------------- empresa
    def _empresa(self):
        empresa, creada = Empresa.objects.get_or_create(
            nombre=EMPRESA_NOMBRE, defaults={"rut": EMPRESA_RUT}
        )
        self.stdout.write(
            f"Empresa: {empresa.nombre} ({'creada' if creada else 'ya existía'}) · "
            f"margen {empresa.margen_ganancia_pct}% · transporte ${empresa.precio_transporte_km}/km"
        )
        return empresa

    def _usuarios(self, empresa):
        jefe = None
        for username, password, rol in USUARIOS:
            user = Usuario.objects.filter(username=username).first()
            if user is None:
                # Se construye completo antes del INSERT: la restricción
                # usuario_empresa_y_rol exige superuser, o empresa + rol válidos.
                if rol is None:
                    user = Usuario(
                        username=username, is_staff=True, is_superuser=True,
                        empresa=None, rol=None,
                    )
                else:
                    user = Usuario(username=username, empresa=empresa, rol=rol)
                user.set_password(password)
                user.save()
            if rol == Usuario.Rol.JEFE:
                jefe = user
        return jefe

    # --------------------------------------------------------------- clientes
    def _clientes(self, empresa, cuantos):
        clientes = []
        for i in range(cuantos):
            nombre, telefono, direccion = CLIENTES[i]
            cliente, _ = Cliente.objects.get_or_create(
                empresa=empresa,
                rut=_rut(10_000_000 + i * 111_111),
                defaults={"nombre": nombre, "telefono": telefono, "direccion": direccion},
            )
            clientes.append(cliente)
        self.stdout.write(f"  Clientes: {len(clientes)}")
        return clientes

    # ------------------------------------------------------- cotización/proy.
    def _cotizacion(self, empresa, cliente, jefe, fecha, con_transporte=False):
        """Crea una cotización con 1-3 ventanas al azar y la valoriza."""
        datos = {}
        if con_transporte:
            datos["requiere_transporte"] = True
            datos["distancia_transporte_km"] = Decimal(random.randint(3, 40))
        cot = Cotizacion.objects.create(
            empresa=empresa, cliente=cliente, empleado=jefe, **datos
        )
        for _ in range(random.randint(1, 3)):
            VentanaCotizada.objects.create(
                cotizacion=cot,
                tipo=random.choice(TIPOS),
                color=random.choice(COLORES),
                vidrio=random.choice(VIDRIOS),
                ancho_mm=random.randrange(600, 2001, 50),
                alto_mm=random.randrange(600, 2001, 50),
                cantidad=random.randint(1, 3),
            )
        recalcular_cotizacion(cot)
        Cotizacion.objects.filter(pk=cot.pk).update(fecha_ingreso=fecha)
        return cot

    def _aprobar(self, cot, jefe, fecha):
        Cotizacion.objects.filter(pk=cot.pk).update(
            estado=Cotizacion.Estado.APROBADA, fecha_resolucion=fecha, resuelta_por=jefe
        )
        cot.refresh_from_db()

    def _proyecto(self, cot, jefe, fecha, prod_estado, pago_estado):
        """Crea el proyecto de una cotización aprobada, con sus pagos y fechas."""
        bruto = desglose_iva(cot.total)[2]
        motivo = "Cliente desistió del proyecto." if prod_estado == Proyecto.EstadoProduccion.CANCELADO else ""
        proy = Proyecto.objects.create(
            cotizacion=cot,
            empresa=cot.empresa,
            cliente=cot.cliente,
            estado_produccion=prod_estado,
            motivo_cancelacion=motivo,
            estado_actualizado_en=fecha,
        )
        # Pagos según el estado de pago.
        abonado = 0
        if pago_estado == Proyecto.EstadoPago.PAGADO and bruto > 0:
            abonado = bruto
            self._pago(proy, jefe, bruto, fecha)
        elif pago_estado == Proyecto.EstadoPago.ABONADO and bruto > 1:
            abonado = int(bruto * Decimal(random.choice([0.3, 0.5, 0.7])))
            abonado = max(1, min(abonado, bruto - 1))
            self._pago(proy, jefe, abonado, fecha)
        Proyecto.objects.filter(pk=proy.pk).update(
            estado_pago=pago_estado, monto_abonado=abonado, fecha_creacion=fecha
        )
        return proy

    def _pago(self, proy, jefe, monto, fecha):
        pago = Pago.objects.create(
            proyecto=proy, monto=monto, fecha=fecha.date(), registrado_por=jefe,
            comentario="Pago registrado (demo).",
        )
        Pago.objects.filter(pk=pago.pk).update(creado_en=fecha)

    # ------------------------------------------------------------- poblados
    def _poblar_minimo(self, empresa, jefe):
        ahora = timezone.now()
        clientes = self._clientes(empresa, 2)
        for cliente in clientes:
            # Proyecto 1: entregado y pagado (hace ~3 meses).
            f1 = ahora - timedelta(days=90)
            cot1 = self._cotizacion(empresa, cliente, jefe, f1)
            self._aprobar(cot1, jefe, f1)
            self._proyecto(cot1, jefe, f1, Proyecto.EstadoProduccion.ENTREGADO, Proyecto.EstadoPago.PAGADO)
            # Proyecto 2: en fabricación, abonado (reciente).
            f2 = ahora - timedelta(days=10)
            cot2 = self._cotizacion(empresa, cliente, jefe, f2)
            self._aprobar(cot2, jefe, f2)
            self._proyecto(cot2, jefe, f2, Proyecto.EstadoProduccion.EN_FABRICACION, Proyecto.EstadoPago.ABONADO)
        self.stdout.write("  Mínimo: 2 clientes, 4 proyectos.")

    def _poblar_extenso(self, empresa, jefe):
        ahora = timezone.now()
        clientes = self._clientes(empresa, 10)

        # 4 cotizaciones pendientes (sin proyecto).
        for _ in range(4):
            f = ahora - timedelta(days=random.randint(1, 20))
            self._cotizacion(empresa, random.choice(clientes), jefe, f, con_transporte=random.random() < 0.3)
        self.stdout.write("  4 cotizaciones pendientes.")

        # 65 proyectos entregados y pagados, de hace 2 a 12 meses.
        for _ in range(65):
            f = ahora - timedelta(days=random.randint(60, 365))
            cot = self._cotizacion(empresa, random.choice(clientes), jefe, f, con_transporte=random.random() < 0.3)
            self._aprobar(cot, jefe, f)
            self._proyecto(cot, jefe, f, Proyecto.EstadoProduccion.ENTREGADO, Proyecto.EstadoPago.PAGADO)
        self.stdout.write("  65 proyectos entregados y pagados (2-12 meses).")

        # 15 recientes (< 2 meses) con estados variados.
        prod_estados = [
            Proyecto.EstadoProduccion.POR_INICIAR,
            Proyecto.EstadoProduccion.EN_FABRICACION,
            Proyecto.EstadoProduccion.TERMINADO,
            Proyecto.EstadoProduccion.ENTREGADO,
            Proyecto.EstadoProduccion.CANCELADO,
        ]
        pago_estados = [
            Proyecto.EstadoPago.PENDIENTE,
            Proyecto.EstadoPago.ABONADO,
            Proyecto.EstadoPago.PAGADO,
        ]
        for i in range(15):
            f = ahora - timedelta(days=random.randint(1, 59))
            cot = self._cotizacion(empresa, random.choice(clientes), jefe, f, con_transporte=random.random() < 0.3)
            self._aprobar(cot, jefe, f)
            prod = prod_estados[i % len(prod_estados)]
            # Cancelado suele quedar sin pago; el resto, pago variado.
            pago = Proyecto.EstadoPago.PENDIENTE if prod == Proyecto.EstadoProduccion.CANCELADO else random.choice(pago_estados)
            self._proyecto(cot, jefe, f, prod, pago)
        self.stdout.write("  15 proyectos recientes con estados variados.")
