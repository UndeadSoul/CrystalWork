"""Tests del detalle de pagos (abonos) de un proyecto. Ver projects/pagos.py."""

from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from core.catalog import asegurar_catalogo
from core.models import CambioRegistro, Cliente, Cotizacion
from users.models import Empresa, Usuario

from .models import Proyecto

TOTAL_NETO = 100_000  # bruto = 119.000


class EscenarioProyecto(APITestCase):
    """Empresa con jefe y operario, otra empresa, y un proyecto (neto 100.000)."""

    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nombre="Empresa Alfa")
        asegurar_catalogo(cls.empresa)
        cls.jefe = Usuario.objects.create(
            username="jefe1", empresa=cls.empresa, rol=Usuario.Rol.JEFE
        )
        cls.operario = Usuario.objects.create(
            username="operario1", empresa=cls.empresa, rol=Usuario.Rol.OPERARIO
        )
        cls.otra = Empresa.objects.create(nombre="Empresa Beta")
        cls.jefe_otra = Usuario.objects.create(
            username="jefe.beta", empresa=cls.otra, rol=Usuario.Rol.JEFE
        )
        cliente = Cliente.objects.create(
            empresa=cls.empresa, nombre="Cliente Alfa", rut="11.111.111-1"
        )
        cot = Cotizacion.objects.create(
            empresa=cls.empresa,
            cliente=cliente,
            empleado=cls.operario,
            estado=Cotizacion.Estado.APROBADA,
            total=TOTAL_NETO,
        )
        cls.proyecto = Proyecto.objects.create(
            cotizacion=cot, empresa=cls.empresa, cliente=cliente
        )

    def setUp(self):
        self.cliente = APIClient()
        self.como(self.jefe)
        self.url = f"/api/proyectos/{self.proyecto.id}/"

    def como(self, usuario):
        self.cliente.force_authenticate(usuario)

    def pagar(self, monto, fecha=None, comentario=""):
        return self.cliente.post(
            f"{self.url}pagos/",
            {
                "monto": monto,
                "fecha": str(fecha or timezone.localdate()),
                "comentario": comentario,
            },
            format="json",
        )

    def anular(self, pago_id, motivo="Pago duplicado"):
        return self.cliente.post(
            f"{self.url}pagos/{pago_id}/anular/", {"motivo": motivo}, format="json"
        )


class PagosTests(EscenarioProyecto):
    def test_pagos_parciales_y_total(self):
        r = self.pagar(50_000, comentario="Abono inicial")
        self.assertEqual(r.status_code, 201)
        d = r.json()
        self.assertEqual((d["estado_pago"], d["monto_abonado"], d["saldo"]), ("ABONADO", "50000", 69_000))
        self.assertEqual(d["pagos"][0]["registrado_por_nombre"], "jefe1")

        d = self.pagar(69_000).json()
        self.assertEqual((d["estado_pago"], d["monto_abonado"], d["saldo"]), ("PAGADO", "119000", 0))
        self.assertEqual(len(d["pagos"]), 2)

    def test_dos_personas_registran_pagos_sin_pisarse(self):
        """Antes el abono era un total editable: el segundo pisaba al primero."""
        self.pagar(30_000)
        self.como(self.operario)
        d = self.pagar(20_000).json()
        self.assertEqual(d["monto_abonado"], "50000")

    def test_no_supera_el_saldo(self):
        self.pagar(100_000)
        r = self.pagar(20_000)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Supera el saldo pendiente ($19.000)", r.json()["monto"][0])
        self.pagar(19_000)
        r = self.pagar(1)
        self.assertEqual(r.status_code, 400)
        self.assertIn("pagado por completo", r.json()["monto"][0])

    def test_validaciones(self):
        hoy = timezone.localdate()
        casos = [
            ({"monto": 0}, "monto"),
            ({"monto": -5}, "monto"),
            ({"monto": "10.5"}, "monto"),
            ({"monto": 1000, "fecha": str(hoy + timedelta(days=1))}, "fecha"),
            ({"monto": 1000, "fecha": "2000-01-01"}, "fecha"),
            ({"monto": 1000, "comentario": "<script>"}, "comentario"),
        ]
        for datos, campo in casos:
            with self.subTest(datos=datos):
                r = self.cliente.post(
                    f"{self.url}pagos/", {"fecha": str(hoy), **datos}, format="json"
                )
                self.assertEqual(r.status_code, 400)
                self.assertIn(campo, r.json())
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.monto_abonado, 0)

    def test_anular_recalcula_y_queda_en_el_historial(self):
        self.pagar(100_000)
        d = self.pagar(19_000).json()
        self.assertEqual(d["estado_pago"], "PAGADO")
        pago_id = d["pagos"][1]["id"]

        r = self.anular(pago_id)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual((d["estado_pago"], d["monto_abonado"], d["saldo"]), ("ABONADO", "100000", 19_000))
        anulado = d["pagos"][1]
        self.assertTrue(anulado["anulado"])
        self.assertEqual(anulado["anulado_por_nombre"], "jefe1")
        self.assertEqual(anulado["motivo_anulacion"], "Pago duplicado")
        campos = set(
            CambioRegistro.objects.filter(objeto_id=self.proyecto.id).values_list("campo", flat=True)
        )
        self.assertTrue({"Pago registrado", "Pago anulado", "Pago"} <= campos)

    def test_no_se_anula_dos_veces(self):
        pago_id = self.pagar(1_000).json()["pagos"][0]["id"]
        self.assertEqual(self.anular(pago_id).status_code, 200)
        r = self.anular(pago_id)
        self.assertEqual(r.status_code, 409)
        self.assertIn("ya fue anulado por jefe1", r.json()["detail"])

    def test_anular_requiere_motivo_y_ser_jefe(self):
        pago_id = self.pagar(1_000).json()["pagos"][0]["id"]
        self.assertEqual(self.anular(pago_id, motivo="").status_code, 400)
        self.como(self.operario)
        self.assertEqual(self.anular(pago_id).status_code, 403)

    def test_estado_de_pago_no_se_edita_directo(self):
        r = self.cliente.patch(
            self.url, {"estado_pago": "PAGADO", "monto_abonado": 119000}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.proyecto.refresh_from_db()
        self.assertEqual(self.proyecto.estado_pago, "PENDIENTE")
        self.assertEqual(self.proyecto.monto_abonado, 0)

    def test_otra_empresa_no_registra_pagos(self):
        self.como(self.jefe_otra)
        self.assertEqual(self.pagar(1_000).status_code, 404)


class CancelacionYPdfTests(EscenarioProyecto):
    """Estado Cancelado y exportacion a PDF (reutiliza el escenario de pagos)."""

    def cancelar(self, motivo="El cliente desistió de la compra"):
        return self.cliente.patch(
            self.url,
            {"estado_produccion": "CANCELADO", "motivo_cancelacion": motivo},
            format="json",
        )

    def test_cancelar_exige_motivo(self):
        r = self.cliente.patch(self.url, {"estado_produccion": "CANCELADO"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("motivo_cancelacion", r.json())
        r = self.cancelar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["motivo_cancelacion"], "El cliente desistió de la compra")
        cambio = CambioRegistro.objects.filter(objeto_id=self.proyecto.id, campo="Fabricación").first()
        self.assertIn("Cancelado: El cliente desistió", cambio.valor_nuevo)

    def test_solo_el_jefe_cancela_y_reactiva(self):
        self.como(self.operario)
        self.assertEqual(self.cancelar().status_code, 403)
        self.como(self.jefe)
        self.assertEqual(self.cancelar().status_code, 200)
        self.como(self.operario)
        r = self.cliente.patch(self.url, {"estado_produccion": "EN_FABRICACION"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.como(self.jefe)
        r = self.cliente.patch(self.url, {"estado_produccion": "EN_FABRICACION"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["motivo_cancelacion"], "")

    def test_cancelado_no_recibe_pagos_ni_cuenta_como_facturado(self):
        self.pagar(10_000)
        resumen = lambda: self.cliente.get("/api/analytics/resumen/").json()["kpis"]  # noqa: E731
        self.assertEqual(resumen()["facturado"], 119_000)
        self.cancelar()
        r = self.pagar(1_000)
        self.assertEqual(r.status_code, 400)
        self.assertIn("cancelado", r.json()["detail"][0])
        self.assertEqual(resumen()["facturado"], 0)
        self.assertEqual(resumen()["por_cobrar"], 0)

    def test_pdf_cotizacion_proyecto_y_hoja_de_corte(self):
        urls = [
            f"/api/cotizaciones/{self.proyecto.cotizacion_id}/pdf/",
            f"{self.url}pdf/",
            f"{self.url}hoja-corte/pdf/",
        ]
        self.pagar(1_000, comentario="Abono inicial")
        self.cancelar()
        for url in urls:
            with self.subTest(url=url):
                r = self.cliente.get(url)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r["Content-Type"], "application/pdf")
                self.assertIn("attachment", r["Content-Disposition"])
                self.assertTrue(r.content.startswith(b"%PDF"))

    def test_pdf_respeta_permisos(self):
        url = f"{self.url}pdf/"
        self.como(self.jefe_otra)
        self.assertEqual(self.cliente.get(url).status_code, 404)
        admin = Usuario.objects.create(username="admin.sistema", is_superuser=True, is_staff=True)
        self.como(admin)
        self.assertEqual(self.cliente.get(url).status_code, 403)
