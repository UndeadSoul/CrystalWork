"""Tests de aislamiento entre empresas y de permisos por rol.

Escenario: dos empresas (A y B) con su jefe, un operario en A y el
administrador del sistema. A tiene cliente, cotizacion aprobada (proyecto),
catalogo y un registro de cambio. Se verifica que:
  - El administrador no accede a datos operativos (solo empresas/usuarios).
  - Un usuario de B no ve ni modifica nada de A (404 / listas vacias).
  - El operario no accede a precios, finanzas ni gestion de usuarios.
  - Usuario o empresa desactivados no pueden usar la API.
"""

from rest_framework.test import APITestCase

from core.catalog import asegurar_catalogo
from core.models import (
    CambioRegistro,
    Cliente,
    Cotizacion,
    PlanchaVidrio,
    PrecioSerie,
    SerieAluminio,
    VentanaCotizada,
)
from projects.models import Proyecto

from .models import Empresa, Usuario

CLAVE = "Ventana-Segura-2026"

# Endpoints de datos operativos (listas / vistas sin id).
OPERATIVOS = [
    "/api/clientes/",
    "/api/cotizaciones/",
    "/api/cotizaciones/opciones/",
    "/api/proyectos/",
    "/api/analytics/resumen/",
    "/api/analytics/ingresos/",
    "/api/catalogo/series/",
    "/api/catalogo/perfiles-serie/",
    "/api/catalogo/precios-serie/",
    "/api/catalogo/planchas/",
    "/api/catalogo/insumos/",
    "/api/catalogo/empresa/",
    "/api/catalogo/cambios/",
]


def crear_usuario(username, empresa=None, rol=None, superuser=False):
    u = Usuario(
        username=username,
        first_name="Nombre",
        last_name="Apellido",
        empresa=empresa,
        rol=rol,
        is_superuser=superuser,
        is_staff=superuser,
    )
    u.set_password(CLAVE)
    u.save()
    return u


class BaseEscenario(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa_a = Empresa.objects.create(nombre="Empresa Alfa")
        cls.empresa_b = Empresa.objects.create(nombre="Empresa Beta")
        for e in (cls.empresa_a, cls.empresa_b):
            asegurar_catalogo(e)

        cls.admin = crear_usuario("admin.sistema", superuser=True)
        cls.jefe_a = crear_usuario("jefe.a", cls.empresa_a, Usuario.Rol.JEFE)
        cls.operario_a = crear_usuario("operario.a", cls.empresa_a, Usuario.Rol.OPERARIO)
        cls.jefe_b = crear_usuario("jefe.b", cls.empresa_b, Usuario.Rol.JEFE)

        # Datos de la empresa A.
        cls.cliente_a = Cliente.objects.create(
            empresa=cls.empresa_a, nombre="Cliente Alfa", rut="11.111.111-1"
        )
        cls.plancha_a = PlanchaVidrio.objects.create(
            empresa=cls.empresa_a,
            tipo_vidrio="INCOLORO_4",
            ancho_plancha_m="2.4",
            alto_plancha_m="3.6",
            precio=50000,
        )
        cls.serie_a = SerieAluminio.objects.get(empresa=cls.empresa_a, codigo="L20")
        cls.perfil_a = cls.serie_a.perfiles.first()
        cls.precio_a = PrecioSerie.objects.create(
            serie=cls.serie_a, color="MATE", precio=100000
        )
        cls.insumo_a = cls.empresa_a.insumos.first()
        cls.cotizacion_a = Cotizacion.objects.create(
            empresa=cls.empresa_a,
            cliente=cls.cliente_a,
            empleado=cls.operario_a,
            estado=Cotizacion.Estado.APROBADA,
        )
        VentanaCotizada.objects.create(
            cotizacion=cls.cotizacion_a,
            tipo="Linea20simple",
            color="MATE",
            vidrio="INCOLORO_4",
            ancho_mm=1200,
            alto_mm=1000,
        )
        cls.proyecto_a = Proyecto.objects.create(
            cotizacion=cls.cotizacion_a, empresa=cls.empresa_a, cliente=cls.cliente_a
        )
        CambioRegistro.objects.create(
            empresa=cls.empresa_a,
            categoria=CambioRegistro.Categoria.PRECIO,
            objeto_tipo="insumo",
            objeto_label="Felpa",
            campo="Precio paquete",
            valor_anterior="1",
            valor_nuevo="2",
        )

    def como(self, usuario):
        self.client.force_authenticate(usuario)


class AdministradorSinDatosOperativosTests(BaseEscenario):
    def test_no_accede_a_datos_operativos(self):
        self.como(self.admin)
        for url in OPERATIVOS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_no_accede_a_objetos_de_una_empresa(self):
        self.como(self.admin)
        urls = [
            f"/api/clientes/{self.cliente_a.id}/",
            f"/api/cotizaciones/{self.cotizacion_a.id}/",
            f"/api/proyectos/{self.proyecto_a.id}/",
            f"/api/proyectos/{self.proyecto_a.id}/hoja-corte/",
            f"/api/catalogo/perfiles-serie/{self.perfil_a.id}/",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        r = self.client.post(f"/api/cotizaciones/{self.cotizacion_a.id}/aprobar/")
        self.assertEqual(r.status_code, 403)

    def test_si_gestiona_empresas_y_usuarios(self):
        self.como(self.admin)
        for url in ("/api/me/", "/api/empresas/", "/api/usuarios/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class AislamientoEntreEmpresasTests(BaseEscenario):
    def test_listas_no_muestran_datos_de_otra_empresa(self):
        self.como(self.jefe_b)
        for url in ("/api/clientes/", "/api/cotizaciones/", "/api/proyectos/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).json(), [])
        self.assertEqual(self.client.get("/api/catalogo/cambios/").json(), [])
        series = self.client.get("/api/catalogo/series/").json()
        self.assertTrue(series)
        self.assertTrue(all(s["id"] != self.serie_a.id for s in series))
        planchas = self.client.get("/api/catalogo/planchas/").json()
        self.assertNotIn(self.plancha_a.id, [p["id"] for p in planchas])

    def test_objetos_de_otra_empresa_son_404(self):
        self.como(self.jefe_b)
        urls = [
            f"/api/clientes/{self.cliente_a.id}/",
            f"/api/cotizaciones/{self.cotizacion_a.id}/",
            f"/api/proyectos/{self.proyecto_a.id}/",
            f"/api/proyectos/{self.proyecto_a.id}/hoja-corte/",
            f"/api/proyectos/{self.proyecto_a.id}/cambios/",
            f"/api/catalogo/series/{self.serie_a.id}/",
            f"/api/catalogo/perfiles-serie/{self.perfil_a.id}/",
            f"/api/catalogo/precios-serie/{self.precio_a.id}/",
            f"/api/catalogo/planchas/{self.plancha_a.id}/",
            f"/api/catalogo/insumos/{self.insumo_a.id}/",
            f"/api/usuarios/{self.operario_a.id}/",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_no_modifica_datos_de_otra_empresa(self):
        self.como(self.jefe_b)
        cambios = [
            ("patch", f"/api/clientes/{self.cliente_a.id}/", {"nombre": "Hackeado"}),
            ("patch", f"/api/proyectos/{self.proyecto_a.id}/", {"estado_produccion": "ENTREGADO"}),
            ("patch", f"/api/catalogo/precios-serie/{self.precio_a.id}/", {"precio": 1}),
            ("patch", f"/api/catalogo/insumos/{self.insumo_a.id}/", {"precio_paquete": 1}),
            ("post", f"/api/cotizaciones/{self.cotizacion_a.id}/recalcular/", {}),
            ("post", f"/api/usuarios/{self.operario_a.id}/desactivar/", {}),
        ]
        for metodo, url, data in cambios:
            with self.subTest(url=url):
                r = getattr(self.client, metodo)(url, data, format="json")
                self.assertEqual(r.status_code, 404)
        self.cliente_a.refresh_from_db()
        self.assertEqual(self.cliente_a.nombre, "Cliente Alfa")
        self.precio_a.refresh_from_db()
        self.assertEqual(self.precio_a.precio, 100000)
        self.operario_a.refresh_from_db()
        self.assertTrue(self.operario_a.is_active)

    def test_no_cotiza_con_cliente_de_otra_empresa(self):
        self.como(self.jefe_b)
        r = self.client.post(
            "/api/cotizaciones/",
            {
                "cliente": self.cliente_a.id,
                "ventanas": [
                    {
                        "tipo": "Linea20simple",
                        "color": "MATE",
                        "vidrio": "INCOLORO_4",
                        "ancho_mm": 1000,
                        "alto_mm": 1000,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("cliente", r.json())

    def test_dashboard_solo_cuenta_su_empresa(self):
        self.como(self.jefe_b)
        kpis = self.client.get("/api/analytics/resumen/").json()["kpis"]
        self.assertTrue(all(not v for v in kpis.values() if isinstance(v, (int, float))))
        self.como(self.jefe_a)
        kpis_a = self.client.get("/api/analytics/resumen/").json()["kpis"]
        self.assertNotEqual(kpis, kpis_a)


class PermisosPorRolTests(BaseEscenario):
    def test_operario_sin_precios_finanzas_ni_usuarios(self):
        self.como(self.operario_a)
        for url in (
            "/api/catalogo/series/",
            "/api/catalogo/empresa/",
            "/api/catalogo/cambios/",
            "/api/analytics/ingresos/",
            "/api/usuarios/",
            "/api/empresas/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        pendiente = Cotizacion.objects.create(
            empresa=self.empresa_a, cliente=self.cliente_a, empleado=self.operario_a
        )
        r = self.client.post(f"/api/cotizaciones/{pendiente.id}/aprobar/")
        self.assertEqual(r.status_code, 403)

    def test_operario_si_trabaja_con_su_empresa(self):
        self.como(self.operario_a)
        for url in ("/api/clientes/", "/api/cotizaciones/", "/api/proyectos/"):
            with self.subTest(url=url):
                self.assertEqual(len(self.client.get(url).json()), 1)

    def test_jefe_no_gestiona_empresas(self):
        self.como(self.jefe_a)
        self.assertEqual(self.client.get("/api/empresas/").status_code, 403)

    def test_jefe_solo_ve_sus_operarios(self):
        self.como(self.jefe_a)
        usernames = [u["username"] for u in self.client.get("/api/usuarios/").json()]
        self.assertEqual(usernames, ["operario.a"])


class DesactivacionTests(BaseEscenario):
    def login(self, username):
        return self.client.post(
            "/api/token/", {"username": username, "password": CLAVE}, format="json"
        )

    def test_usuario_desactivado_no_inicia_sesion_ni_usa_sesion_abierta(self):
        access = self.login("operario.a").json()["access"]
        self.operario_a.is_active = False
        self.operario_a.save()
        self.assertEqual(self.login("operario.a").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/me/").status_code, 401)

    def test_empresa_desactivada_bloquea_a_sus_usuarios(self):
        access = self.login("jefe.a").json()["access"]
        self.empresa_a.activa = False
        self.empresa_a.save()
        r = self.login("jefe.a")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["code"], "empresa_inactiva")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/clientes/").status_code, 401)
        # La otra empresa sigue funcionando.
        self.assertEqual(self.login("jefe.b").status_code, 200)
