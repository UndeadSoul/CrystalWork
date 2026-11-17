"""Tests del sistema de alertas (app alerts). Alertas calculadas en vivo."""

from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from core.models import Cliente, Cotizacion
from projects.models import Proyecto
from users.models import Empresa, Usuario


class AlertasTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nombre="Empresa Alfa")
        cls.jefe = Usuario.objects.create(
            username="jefe1", empresa=cls.empresa, rol=Usuario.Rol.JEFE
        )
        cls.operario = Usuario.objects.create(
            username="op1", empresa=cls.empresa, rol=Usuario.Rol.OPERARIO
        )
        cls.cli = Cliente.objects.create(
            empresa=cls.empresa, nombre="Cliente Alfa", rut="11.111.111-1"
        )

        # Cotizacion pendiente desde hace 10 dias (fecha_ingreso es auto_now_add,
        # se fuerza con update).
        cot_pend = Cotizacion.objects.create(
            empresa=cls.empresa,
            cliente=cls.cli,
            empleado=cls.operario,
            estado=Cotizacion.Estado.PENDIENTE,
            total=100_000,
        )
        Cotizacion.objects.filter(pk=cot_pend.pk).update(
            fecha_ingreso=timezone.now() - timedelta(days=10)
        )

        # Proyecto estancado: ultimo cambio de estado hace 30 dias.
        cot_apr = Cotizacion.objects.create(
            empresa=cls.empresa,
            cliente=cls.cli,
            empleado=cls.operario,
            estado=Cotizacion.Estado.APROBADA,
            total=100_000,
        )
        cls.proy = Proyecto.objects.create(
            cotizacion=cot_apr,
            empresa=cls.empresa,
            cliente=cls.cli,
            estado_actualizado_en=timezone.now() - timedelta(days=30),
        )

    def setUp(self):
        self.api = APIClient()

    def test_jefe_ve_alertas(self):
        self.api.force_authenticate(self.jefe)
        r = self.api.get("/api/alertas/")
        self.assertEqual(r.status_code, 200)
        tipos = {a["tipo"] for a in r.data["alertas"]}
        self.assertIn("cotizacion_pendiente", tipos)
        self.assertIn("proyecto_estancado", tipos)
        self.assertEqual(r.data["total"], len(r.data["alertas"]))

    def test_resumen_sin_lista(self):
        self.api.force_authenticate(self.jefe)
        r = self.api.get("/api/alertas/resumen/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.data["total"], 2)
        self.assertNotIn("alertas", r.data)

    def test_operario_no_accede(self):
        self.api.force_authenticate(self.operario)
        self.assertEqual(self.api.get("/api/alertas/").status_code, 403)

    def test_aislamiento_por_empresa(self):
        otra = Empresa.objects.create(nombre="Empresa Beta")
        jefe_beta = Usuario.objects.create(
            username="jefe.beta", empresa=otra, rol=Usuario.Rol.JEFE
        )
        self.api.force_authenticate(jefe_beta)
        r = self.api.get("/api/alertas/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total"], 0)
