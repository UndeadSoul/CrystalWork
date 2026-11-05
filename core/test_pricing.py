"""Tests del calculo de precios (core/pricing.py).

Catalogo con valores redondos para que cada total esperado se pueda verificar
a mano (ver los calculos en cada constante):

  Aluminio  precio del metro de perfil = precio_serie * (peso_perfil / peso_serie) / largo_tira
            L20: 60.000 * (1 / 10) / 6 = $1.000 por metro (riel inferior simple: peso 2 -> $2.000/m)
            L25: 120.000 * (1 / 10) / 6 = $2.000 por metro
  Vidrio    plancha de 2 x 3 m a $60.000 -> $10.000/m2, con 20% de merma
            burlete $1.000 el rollo de 10 m -> $100/m
  Agregados felpa $100/m, caracol $300, tornillo $10 c/u (paquete de 100 a $1.000), silicona $2.000
            L20: pestillo $500, rodamiento $200 | L25: pestillo $9.000, rodamiento $7.000
            (precios muy distintos para detectar si se usa el insumo de la otra linea)

Ventana base: 1000 x 1000 mm, color Mate, vidrio Incoloro 4 mm.
"""

from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from core.catalog import asegurar_catalogo
from core.models import Cliente, Insumo, PlanchaVidrio, PrecioSerie, SerieAluminio
from core.pricing import (
    PricingError,
    agregados_usados,
    calcular_costo_ventana,
    desglose_iva,
)
from projects.windowstypes import calc_windtype_profiles
from users.models import Empresa, Usuario

# Precios por insumo: (precio_paquete, cantidad_paquete).
INSUMOS = {
    "FELPA": (100, 1),
    "BURLETE": (1000, 10),
    "PESTILLO_L20": (500, 1),
    "PESTILLO_L25": (9000, 1),
    "CARACOL": (300, 1),
    "RODAMIENTO_L20": (200, 1),
    "RODAMIENTO_L25": (7000, 1),
    "TORNILLO": (1000, 100),
    "SILICONA": (2000, 1),
}

# --- Costos esperados de la ventana base (1000 x 1000 mm) ---

# Vidrio, igual para todos los tipos:
#   cristal: 2 hojas de (1/2 - 0,054) x (1 - 0,107) = 2 x 0,446 x 0,893 = 0,796556 m2
#   0,796556 m2 x $10.000 x 1,20 de merma = $9.558,672
#   burlete: 1 x 2 + 1 x 4 = 6 m x $100 = $600
VIDRIO = Decimal("10158.672")

# Agregados: felpa (6 + 6) / 10 = 1,2 m x $100 = 120; 2 pestillos; caracol 300;
# 4 rodamientos; 24 tornillos x 10 = 240; silicona 2.000.
AGREGADOS_L20 = 120 + 2 * 500 + 300 + 4 * 200 + 240 + 2000  # 4.460
AGREGADOS_L25 = 120 + 2 * 9000 + 300 + 4 * 7000 + 240 + 2000  # 48.660

# Aluminio (metros de perfil x precio del metro):
#   Linea20lluvia: rieles 2 x 0,988 + zocalos/cabezales 4 x 0,5 + batientes/traslapos 4 x 0,965
#                  + jambas 2 x 1 = 9,836 m x $1.000
#   Linea20simple: el riel inferior es el "simple" ($2.000/m) y el descuento de alto es 0,027:
#                  0,988 + 0,988 x 2 + 2 + 4 x 0,973 + 2 = 10,856 m-equivalentes x $1.000
#   Linea25lluvia: rieles 2 x 0,984 + 2 + 4 x 0,955 + 2 = 9,788 m x $2.000
ALUMINIO = {
    "Linea20lluvia": Decimal("9836"),
    "Linea20simple": Decimal("10856"),
    "Linea25lluvia": Decimal("19576"),
}


def redondear(valor):
    """Redondeo a peso, mitad hacia arriba (como core/pricing.py)."""
    return int(Decimal(valor).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))


class EscenarioPrecios(APITestCase):
    """Empresa con el catalogo completo y valores redondos (ver docstring)."""

    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(
            nombre="Empresa Alfa", margen_ganancia_pct=20, precio_transporte_km=1000
        )
        asegurar_catalogo(cls.empresa)
        for codigo, precio in (("L20", 60_000), ("L25", 120_000)):
            serie = SerieAluminio.objects.get(empresa=cls.empresa, codigo=codigo)
            serie.peso_total_kg = 10
            serie.save()
            serie.perfiles.update(peso_kg=1, largo_tira_m=6)
            serie.perfiles.filter(nombre="Riel inferior simple").update(peso_kg=2)
            PrecioSerie.objects.create(serie=serie, color="MATE", precio=precio)
        for codigo, (precio, cantidad) in INSUMOS.items():
            Insumo.objects.filter(empresa=cls.empresa, codigo=codigo).update(
                precio_paquete=precio, cantidad_paquete=cantidad
            )
        PlanchaVidrio.objects.create(
            empresa=cls.empresa,
            tipo_vidrio="INCOLORO_4",
            ancho_plancha_m=2,
            alto_plancha_m=3,
            precio=60_000,
        )
        cls.jefe = Usuario.objects.create(
            username="jefe1", empresa=cls.empresa, rol=Usuario.Rol.JEFE
        )
        cls.cliente = Cliente.objects.create(
            empresa=cls.empresa, nombre="Cliente Alfa", rut="11.111.111-1"
        )

    def costo(self, tipo="Linea20lluvia", color="MATE", vidrio="INCOLORO_4", ancho=1000, alto=1000):
        return calcular_costo_ventana(self.empresa, tipo, color, vidrio, ancho, alto)

    def insumo(self, codigo):
        return Insumo.objects.get(empresa=self.empresa, codigo=codigo)


class CostoVentanaTests(EscenarioPrecios):
    def test_desglose_de_una_ventana(self):
        r = self.costo()
        self.assertEqual(r["costo_aluminio"], 9836)
        self.assertEqual(r["costo_vidrio"], 10159)
        self.assertEqual(r["costo_agregados"], 4460)
        # El total redondea la suma sin redondear (24.454,672), no la suma de redondeos.
        self.assertEqual(r["costo_total"], 24455)

    def test_cada_tipo_usa_su_serie_y_sus_perfiles(self):
        casos = {
            "Linea20lluvia": ALUMINIO["Linea20lluvia"] + VIDRIO + AGREGADOS_L20,
            "Linea20simple": ALUMINIO["Linea20simple"] + VIDRIO + AGREGADOS_L20,
            "Linea25lluvia": ALUMINIO["Linea25lluvia"] + VIDRIO + AGREGADOS_L25,
        }
        for tipo, esperado in casos.items():
            with self.subTest(tipo=tipo):
                r = self.costo(tipo)
                self.assertEqual(r["costo_aluminio"], ALUMINIO[tipo])
                self.assertEqual(r["costo_total"], redondear(esperado))

    def test_riel_simple_usa_el_perfil_riel_inferior_simple(self):
        """Si se sube el precio del riel inferior simple, solo cambian los tipos
        "riel simple"; los "riel lluvia" usan el Riel Inferior estandar."""
        serie = SerieAluminio.objects.get(empresa=self.empresa, codigo="L20")
        serie.perfiles.filter(nombre="Riel inferior simple").update(peso_kg=3)
        # 0,988 m x $1.000 adicional por metro.
        self.assertEqual(self.costo("Linea20simple")["costo_aluminio"], 10856 + 988)
        self.assertEqual(self.costo("Linea20lluvia")["costo_aluminio"], 9836)

    def test_dimensiones_cambian_el_costo(self):
        chica = self.costo(ancho=500, alto=500)["costo_total"]
        grande = self.costo(ancho=2000, alto=1500)["costo_total"]
        self.assertLess(chica, self.costo()["costo_total"])
        self.assertGreater(grande, self.costo()["costo_total"])

    def test_iva(self):
        self.assertEqual(desglose_iva(100_000), (100_000, 19_000, 119_000))
        # Redondeo del IVA a peso, mitad hacia arriba: 19% de 50 = 9,5 -> 10.
        self.assertEqual(desglose_iva(50), (50, 10, 60))
        self.assertEqual(desglose_iva(None), (0, 0, 0))


class AgregadosPorLineaTests(EscenarioPrecios):
    """Pestillos y rodamientos dependen de la linea de la ventana (L20 / L25).
    Antes las ventanas L20 no cobraban sus agregados."""

    def test_l20_cobra_sus_agregados(self):
        self.assertEqual(self.costo("Linea20simple")["costo_agregados"], AGREGADOS_L20)
        self.assertEqual(self.costo("Linea20lluvia")["costo_agregados"], AGREGADOS_L20)

    def test_l25_cobra_sus_agregados(self):
        self.assertEqual(self.costo("Linea25simple")["costo_agregados"], AGREGADOS_L25)
        self.assertEqual(self.costo("Linea25lluvia")["costo_agregados"], AGREGADOS_L25)

    def test_cada_linea_usa_su_pestillo_y_rodamiento(self):
        codigos = lambda tipo: {c for c, _ in agregados_usados(tipo, Decimal(1), Decimal(1))}  # noqa: E731
        comunes = {"FELPA", "CARACOL", "TORNILLO", "SILICONA"}
        self.assertEqual(codigos("Linea20simple"), comunes | {"PESTILLO_L20", "RODAMIENTO_L20"})
        self.assertEqual(codigos("Linea25lluvia"), comunes | {"PESTILLO_L25", "RODAMIENTO_L25"})

    def test_cambiar_un_insumo_de_una_linea_no_afecta_a_la_otra(self):
        Insumo.objects.filter(empresa=self.empresa, codigo="PESTILLO_L25").update(precio_paquete=1)
        self.assertEqual(self.costo("Linea20lluvia")["costo_agregados"], AGREGADOS_L20)
        self.assertEqual(
            self.costo("Linea25lluvia")["costo_agregados"], AGREGADOS_L25 - 2 * (9000 - 1)
        )

    def test_sin_linea_definida_no_hay_agregados(self):
        self.assertEqual(agregados_usados("Linea42f", Decimal(1), Decimal(1)), [])


class DatosFaltantesTests(EscenarioPrecios):
    """Si falta un dato del catalogo no se inventa un precio: PricingError con
    todo lo que falta, para mostrarlo al jefe."""

    def faltantes(self, **kwargs):
        with self.assertRaises(PricingError) as ctx:
            self.costo(**kwargs)
        return ctx.exception.faltantes

    def test_falta_precio_del_color(self):
        self.assertEqual(self.faltantes(color="BRONCE"), ["Precio de Serie L20 en color BRONCE"])

    def test_falta_peso_de_la_serie(self):
        SerieAluminio.objects.filter(empresa=self.empresa, codigo="L20").update(peso_total_kg=0)
        self.assertEqual(self.faltantes(), ["Pesos de perfiles de Serie L20"])

    def test_falta_plancha_de_vidrio(self):
        self.assertEqual(self.faltantes(vidrio="BRONCE_4"), ["Plancha de vidrio BRONCE_4"])

    def test_falta_un_insumo(self):
        self.insumo("RODAMIENTO_L20").delete()
        self.assertEqual(self.faltantes(), ["Insumo RODAMIENTO_L20"])
        # El de la otra linea no se pide.
        self.assertEqual(self.costo("Linea25lluvia")["costo_agregados"], AGREGADOS_L25)

    def test_tipo_sin_serie(self):
        self.assertIn("No hay serie definida para el tipo Linea42f", self.faltantes(tipo="Linea42f"))

    def test_se_informan_todos_los_faltantes_juntos(self):
        self.insumo("BURLETE").delete()
        self.assertEqual(
            self.faltantes(color="BRONCE", vidrio="BRONCE_4"),
            ["Precio de Serie L20 en color BRONCE", "Plancha de vidrio BRONCE_4", "Insumo BURLETE"],
        )

    def test_precio_en_cero_no_es_faltante(self):
        """El 0 significa "sin precio" (se avisara en la fase de alertas): hoy se
        calcula como costo 0, no como dato faltante."""
        Insumo.objects.filter(empresa=self.empresa, codigo="SILICONA").update(precio_paquete=0)
        self.assertEqual(self.costo()["costo_agregados"], AGREGADOS_L20 - 2000)


class TotalCotizacionTests(EscenarioPrecios):
    """De punta a punta por la API: margen, cantidad, transporte, monto agregado
    e IVA."""

    def setUp(self):
        self.client.force_authenticate(self.jefe)

    def ventana(self, **kwargs):
        return {
            "tipo": "Linea20lluvia",
            "color": "MATE",
            "vidrio": "INCOLORO_4",
            "ancho_mm": 1000,
            "alto_mm": 1000,
            "cantidad": 1,
            **kwargs,
        }

    def cotizar(self, ventanas, **datos):
        r = self.client.post(
            "/api/cotizaciones/",
            {"cliente": self.cliente.id, "ventanas": ventanas, **datos},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_margen_y_cantidad(self):
        cot = self.cotizar([self.ventana(cantidad=3)])
        v = cot["ventanas"][0]
        # Costo 24.455 + 20% de margen = 29.346; x 3 = 88.038.
        self.assertEqual(Decimal(v["costo_unitario"]), 24455)
        self.assertEqual(Decimal(v["precio_unitario"]), 29346)
        self.assertEqual(Decimal(v["subtotal"]), 88038)
        self.assertTrue(v["precio_calculado"])
        self.assertEqual(Decimal(cot["total"]), 88038)

    def test_total_con_transporte_monto_agregado_e_iva(self):
        cot = self.cotizar(
            [self.ventana(), self.ventana(tipo="Linea25lluvia", cantidad=2)],
            requiere_transporte=True,
            distancia_transporte_km="12.5",
            comentarios="Instalación en altura",
            monto_agregado=15_000,
        )
        l20 = redondear(redondear(ALUMINIO["Linea20lluvia"] + VIDRIO + AGREGADOS_L20) * Decimal("1.2"))
        l25 = redondear(redondear(ALUMINIO["Linea25lluvia"] + VIDRIO + AGREGADOS_L25) * Decimal("1.2"))
        transporte = 12_500  # 12,5 km x $1.000
        neto = l20 + 2 * l25 + transporte + 15_000
        self.assertEqual(Decimal(cot["costo_transporte"]), transporte)
        self.assertEqual(Decimal(cot["total"]), neto)
        self.assertEqual((cot["iva"], cot["total_bruto"]), desglose_iva(neto)[1:])

    def test_transporte_con_decimales_se_redondea_a_peso(self):
        """12,3 km x $999 = $12.287,7. Antes el total quedaba con centavos en
        memoria: la respuesta al guardar mostraba un bruto $1 menor que al
        volver a abrir la cotizacion."""
        # Sobre la misma instancia que tiene el jefe autenticado (jefe.empresa).
        self.empresa.precio_transporte_km = 999
        self.empresa.save()
        cot = self.cotizar([self.ventana()], requiere_transporte=True, distancia_transporte_km="12.3")
        neto = 29346 + 12288
        self.assertEqual(Decimal(cot["costo_transporte"]), 12288)
        self.assertEqual(Decimal(cot["total"]), neto)
        self.assertEqual((cot["iva"], cot["total_bruto"]), desglose_iva(neto)[1:])
        recargada = self.client.get(f"/api/cotizaciones/{cot['id']}/").json()
        self.assertEqual(
            (recargada["total"], recargada["iva"], recargada["total_bruto"]),
            (cot["total"], cot["iva"], cot["total_bruto"]),
        )

    def test_sin_transporte_no_se_cobra_aunque_haya_distancia(self):
        cot = self.cotizar([self.ventana()], requiere_transporte=False, distancia_transporte_km="40")
        self.assertEqual(Decimal(cot["costo_transporte"]), 0)
        self.assertEqual(Decimal(cot["total"]), 29346)

    def test_ventana_sin_precio_no_suma_al_total(self):
        cot = self.cotizar([self.ventana(), self.ventana(color="BRONCE")])
        sin_precio = cot["ventanas"][1]
        self.assertFalse(sin_precio["precio_calculado"])
        self.assertEqual(Decimal(sin_precio["subtotal"]), 0)
        self.assertEqual(Decimal(cot["total"]), 29346)

    def test_recalcular_toma_los_precios_actuales(self):
        cot = self.cotizar([self.ventana(color="BRONCE")])
        self.assertEqual(Decimal(cot["total"]), 0)
        serie = SerieAluminio.objects.get(empresa=self.empresa, codigo="L20")
        PrecioSerie.objects.create(serie=serie, color="BRONCE", precio=60_000)
        r = self.client.post(
            f"/api/cotizaciones/{cot['id']}/recalcular/", {"version": cot["version"]}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ventanas"][0]["precio_calculado"])
        self.assertEqual(Decimal(r.json()["total"]), 29346)


class PerfilesPorTipoTests(SimpleTestCase):
    """Largos de corte que usa el calculo de aluminio (projects/windowstypes.py)."""

    def test_largos_linea20_lluvia(self):
        largos = {c["name"]: (c["length"], c["cant"]) for c in calc_windtype_profiles("Linea20lluvia", 1000, 1000)}
        self.assertEqual(
            largos,
            {
                "Riel superior": (0.988, 1),
                "Riel Inferior": (0.988, 1),
                "Zocalo": (0.5, 2),
                "Cabezal": (0.5, 2),
                "Batiente": (0.965, 2),
                "Traslapo": (0.965, 2),
                "Jamba": (1.0, 2),
            },
        )

    def test_linea42_aun_no_tiene_cortes(self):
        self.assertEqual(calc_windtype_profiles("Linea42f", 1000, 1000), [])
