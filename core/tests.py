"""Tests de concurrencia en cotizaciones (control de versiones optimista).

Dos jefes de la misma empresa trabajan sobre la misma cotizacion pendiente.
Ver core/concurrencia.py.
"""

from unittest import mock

from rest_framework.test import APIClient, APITestCase

from core.catalog import asegurar_catalogo
from core.models import Cliente, Cotizacion, PlanchaVidrio, SerieAluminio
from projects.models import Proyecto
from users.models import Empresa, Usuario

VENTANA = {
    "tipo": "Linea20simple",
    "color": "MATE",
    "vidrio": "INCOLORO_4",
    "ancho_mm": 1200,
    "alto_mm": 1000,
    "cantidad": 1,
}


class ConcurrenciaCotizacionTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nombre="Empresa Alfa")
        asegurar_catalogo(cls.empresa)
        PlanchaVidrio.objects.create(
            empresa=cls.empresa,
            tipo_vidrio="INCOLORO_4",
            ancho_plancha_m="2.4",
            alto_plancha_m="3.6",
            precio=50000,
        )
        cls.jefe1 = Usuario.objects.create(
            username="jefe1", empresa=cls.empresa, rol=Usuario.Rol.JEFE
        )
        cls.jefe2 = Usuario.objects.create(
            username="jefe2", empresa=cls.empresa, rol=Usuario.Rol.JEFE
        )
        cls.cliente = Cliente.objects.create(
            empresa=cls.empresa, nombre="Cliente Alfa", rut="11.111.111-1"
        )

    def setUp(self):
        # Cada jefe en su propio navegador.
        self.jefe_1 = APIClient()
        self.jefe_1.force_authenticate(self.jefe1)
        self.jefe_2 = APIClient()
        self.jefe_2.force_authenticate(self.jefe2)
        r = self.jefe_1.post(
            "/api/cotizaciones/",
            {"cliente": self.cliente.id, "ventanas": [VENTANA]},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.cot = r.json()
        self.url = f"/api/cotizaciones/{self.cot['id']}/"

    # Acciones -------------------------------------------------------

    def editar(self, cliente, version, ventanas=None):
        return cliente.put(
            self.url,
            {
                "cliente": self.cliente.id,
                "ventanas": ventanas or [VENTANA, dict(VENTANA, ancho_mm=2000)],
                "version": version,
            },
            format="json",
        )

    def aprobar(self, cliente, version):
        return cliente.post(f"{self.url}aprobar/", {"version": version}, format="json")

    def rechazar(self, cliente, version):
        return cliente.post(f"{self.url}rechazar/", {"version": version}, format="json")

    def actual(self):
        return Cotizacion.objects.get(pk=self.cot["id"])

    def hay_proyecto(self):
        return Proyecto.objects.filter(cotizacion_id=self.cot["id"]).exists()

    # Tests ------------------------------------------------------------

    def test_editar_incrementa_version_y_registra_autor(self):
        self.assertEqual(self.cot["version"], 1)
        r = self.editar(self.jefe_2, 1)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["version"], 2)
        self.assertEqual(r.json()["modificada_por_nombre"], "jefe2")

    def test_no_se_aprueba_una_version_que_no_se_vio(self):
        """Jefe 2 edita (agrega una ventana); jefe 1 aprueba lo que tenia en
        pantalla (version 1, con una ventana)."""
        self.assertEqual(len(self.cot["ventanas"]), 1)
        self.assertEqual(self.editar(self.jefe_2, 1).status_code, 200)

        r = self.aprobar(self.jefe_1, 1)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["code"], "conflicto_version")
        self.assertIn("modificada por jefe2", r.json()["detail"])
        cot = self.actual()
        self.assertEqual(cot.estado, Cotizacion.Estado.PENDIENTE)
        self.assertEqual(cot.ventanas.count(), 2)
        self.assertFalse(self.hay_proyecto())

        # Tras recargar (version 2) si puede aprobar.
        self.assertEqual(self.aprobar(self.jefe_1, 2).status_code, 200)
        self.assertTrue(self.hay_proyecto())

    def test_no_se_edita_una_cotizacion_ya_aprobada(self):
        self.assertEqual(self.aprobar(self.jefe_1, 1).status_code, 200)
        r = self.editar(self.jefe_2, 1)
        self.assertEqual(r.status_code, 409)
        self.assertIn("aprobada por jefe1", r.json()["detail"])
        self.assertEqual(self.actual().ventanas.count(), 1)

    def test_aprobacion_durante_el_guardado_de_una_edicion(self):
        """Caso simultaneo: la aprobacion llega mientras se guarda la edicion
        (durante el recalculo de precios). Antes dejaba la cotizacion
        Pendiente con un proyecto creado."""
        import core.serializers as cs

        original = cs.recalcular_cotizacion
        respuestas = []

        def recalcular_e_interrumpir(cotizacion):
            if not respuestas:
                respuestas.append(self.aprobar(self.jefe_1, 1))
            return original(cotizacion)

        with mock.patch.object(cs, "recalcular_cotizacion", recalcular_e_interrumpir):
            r = self.editar(self.jefe_2, 1)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(respuestas[0].status_code, 409)
        cot = self.actual()
        self.assertEqual(cot.estado, Cotizacion.Estado.PENDIENTE)
        self.assertEqual(cot.version, 2)
        self.assertEqual(cot.ventanas.count(), 2)
        self.assertFalse(self.hay_proyecto())

    def test_no_se_resuelve_dos_veces(self):
        """Jefe 1 aprueba y jefe 2 rechaza la misma version."""
        self.assertEqual(self.aprobar(self.jefe_1, 1).status_code, 200)
        r = self.rechazar(self.jefe_2, 1)
        self.assertEqual(r.status_code, 409)
        self.assertIn("aprobada por jefe1", r.json()["detail"])
        # Ni siquiera con la version actual: ya no esta pendiente.
        self.assertEqual(self.rechazar(self.jefe_2, 2).status_code, 409)
        self.assertEqual(self.actual().estado, Cotizacion.Estado.APROBADA)
        self.assertTrue(self.hay_proyecto())

    def test_sin_version_se_rechaza(self):
        r = self.jefe_1.post(f"{self.url}aprobar/", {}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("version", r.json())
        self.assertEqual(self.actual().estado, Cotizacion.Estado.PENDIENTE)

    def test_error_de_validacion_no_consume_la_version(self):
        r = self.editar(self.jefe_1, 1, ventanas=[dict(VENTANA, ancho_mm=10)])
        self.assertEqual(r.status_code, 400)
        cot = self.actual()
        self.assertEqual(cot.version, 1)
        self.assertEqual(cot.ventanas.get().ancho_mm, 1200)

    def test_recalcular_no_cambia_una_aprobada(self):
        self.assertEqual(self.aprobar(self.jefe_1, 1).status_code, 200)
        r = self.jefe_1.post(f"{self.url}recalcular/", {"version": 2}, format="json")
        self.assertEqual(r.status_code, 409)


class ConcurrenciaPreciosTests(APITestCase):
    """Dos jefes editan el catalogo con datos cargados en momentos distintos:
    nadie pisa el cambio del otro sin aviso."""

    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nombre="Empresa Alfa")
        asegurar_catalogo(cls.empresa)
        cls.jefe1 = Usuario.objects.create(
            username="jefe1", empresa=cls.empresa, rol=Usuario.Rol.JEFE
        )
        cls.jefe2 = Usuario.objects.create(
            username="jefe2", empresa=cls.empresa, rol=Usuario.Rol.JEFE
        )

    def setUp(self):
        self.jefe_1 = APIClient()
        self.jefe_1.force_authenticate(self.jefe1)
        self.jefe_2 = APIClient()
        self.jefe_2.force_authenticate(self.jefe2)
        self.felpa, self.burlete = (
            self.empresa.insumos.get(codigo="FELPA"),
            self.empresa.insumos.get(codigo="BURLETE"),
        )

    def guardar_insumo(self, cliente, insumo, version, precio):
        return cliente.put(
            f"/api/catalogo/insumos/{insumo.id}/",
            {
                "codigo": insumo.codigo,
                "nombre": insumo.nombre,
                "unidad": insumo.unidad,
                "precio_paquete": precio,
                "cantidad_paquete": "100",
                "version": version,
            },
            format="json",
        )

    def test_no_se_pisa_un_valor_cambiado_por_otro_jefe(self):
        r = self.guardar_insumo(self.jefe_1, self.felpa, 1, 5500)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["version"], 2)

        # Jefe 2 tenia la version 1 en pantalla.
        r = self.guardar_insumo(self.jefe_2, self.felpa, 1, 4000)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["code"], "conflicto_version")
        self.assertIn("jefe1 modificó este valor", r.json()["detail"])
        self.assertEqual(r.json()["actual"]["precio_paquete"], "5500")
        self.felpa.refresh_from_db()
        self.assertEqual(self.felpa.precio_paquete, 5500)

    def test_filas_distintas_no_se_bloquean(self):
        self.assertEqual(self.guardar_insumo(self.jefe_1, self.felpa, 1, 5500).status_code, 200)
        self.assertEqual(self.guardar_insumo(self.jefe_2, self.burlete, 1, 6000).status_code, 200)

    def test_configuracion_general(self):
        url = "/api/catalogo/empresa/"
        r = self.jefe_1.put(url, {"margen_ganancia_pct": "30", "precio_transporte_km": 900, "version": 1}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["version"], 2)
        r = self.jefe_2.put(url, {"margen_ganancia_pct": "10", "precio_transporte_km": 900, "version": 1}, format="json")
        self.assertEqual(r.status_code, 409)
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.margen_ganancia_pct, 30)

    def test_perfil_y_serie(self):
        serie = SerieAluminio.objects.get(empresa=self.empresa, codigo="L20")
        perfil = serie.perfiles.first()
        datos = {"serie": serie.id, "nombre": perfil.nombre, "largo_tira_m": "6"}
        self.assertEqual(
            self.jefe_1.put(f"/api/catalogo/perfiles-serie/{perfil.id}/", {**datos, "peso_kg": "1.2", "version": 1}, format="json").status_code,
            200,
        )
        r = self.jefe_2.put(f"/api/catalogo/perfiles-serie/{perfil.id}/", {**datos, "peso_kg": "2", "version": 1}, format="json")
        self.assertEqual(r.status_code, 409)
        r = self.jefe_2.put(f"/api/catalogo/series/{serie.id}/", {"peso_total_kg": "7", "version": serie.version}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_error_de_validacion_no_consume_la_version(self):
        r = self.guardar_insumo(self.jefe_1, self.felpa, 1, -5)
        self.assertEqual(r.status_code, 400)
        self.felpa.refresh_from_db()
        self.assertEqual(self.felpa.version, 1)

    def test_sin_version_se_rechaza(self):
        r = self.jefe_1.patch(f"/api/catalogo/insumos/{self.felpa.id}/", {"precio_paquete": 1}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("version", r.json())

    def test_mensaje_de_conflicto_en_la_zona_del_usuario(self):
        """La hora del mensaje coincide con la que el usuario ve en pantalla
        (zona de su navegador, cabecera X-Zona-Horaria)."""
        from zoneinfo import ZoneInfo

        from core.models import CambioRegistro

        self.guardar_insumo(self.jefe_1, self.felpa, 1, 5500)
        creado = CambioRegistro.objects.filter(objeto_id=self.felpa.id).latest("creado_en").creado_en
        for zona in ("America/Santiago", "Asia/Tokyo"):
            with self.subTest(zona=zona):
                self.jefe_2.credentials(HTTP_X_ZONA_HORARIA=zona)
                r = self.guardar_insumo(self.jefe_2, self.felpa, 1, 4000)
                esperado = creado.astimezone(ZoneInfo(zona)).strftime("%d-%m-%Y %H:%M")
                self.assertIn(f"({esperado})", r.json()["detail"])
