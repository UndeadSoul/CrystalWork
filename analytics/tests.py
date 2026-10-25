"""Tests de fechas: se agrupan y se registran en hora de Chile (TIME_ZONE),
aunque se guarden en UTC."""

from datetime import date, datetime, timezone as dt_timezone
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from users.models import Empresa, Usuario

from .views import serie_ingresos


def fila(fecha_utc, neto=100_000):
    return {"cotizacion__total": neto, "fecha_creacion": fecha_utc}


class IngresosEnHoraDeChileTests(SimpleTestCase):
    def test_proyecto_de_noche_se_cuenta_en_su_dia_y_mes_local(self):
        # 31-10-2026 23:30 en Chile (UTC-3) = 01-11-2026 02:30 UTC.
        noche = datetime(2026, 11, 1, 2, 30, tzinfo=dt_timezone.utc)
        with mock.patch("analytics.views.timezone.localdate", return_value=date(2026, 11, 15)):
            meses = {s["label"]: s["total"] for s in serie_ingresos("6meses", [fila(noche)])}
        self.assertEqual(meses["oct 26"], 119_000)
        self.assertEqual(meses["nov 26"], 0)

    def test_semana_usa_el_dia_local(self):
        noche = datetime(2026, 11, 1, 2, 30, tzinfo=dt_timezone.utc)
        with mock.patch("analytics.views.timezone.localdate", return_value=date(2026, 11, 1)):
            dias = {s["label"]: s["total"] for s in serie_ingresos("semana", [fila(noche)])}
        self.assertEqual(dias["31/10"], 119_000)
        self.assertEqual(dias["1/11"], 0)


class UltimoIngresoTests(APITestCase):
    def test_iniciar_sesion_registra_el_ultimo_ingreso(self):
        empresa = Empresa.objects.create(nombre="Empresa Alfa")
        u = Usuario(username="jefe1", empresa=empresa, rol=Usuario.Rol.JEFE)
        u.set_password("Ventana-Segura-2026")
        u.save()
        self.assertIsNone(u.last_login)
        r = self.client.post(
            "/api/token/",
            {"username": "jefe1", "password": "Ventana-Segura-2026"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        u.refresh_from_db()
        self.assertIsNotNone(u.last_login)
