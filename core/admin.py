from django.contrib import admin

from .models import (
    Cliente,
    Cotizacion,
    Insumo,
    PerfilIndividual,
    PerfilSerie,
    PlanchaVidrio,
    PrecioPerfilIndividual,
    PrecioSerie,
    SerieAluminio,
    VentanaCotizada,
)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "rut", "telefono", "email")
    list_filter = ("empresa",)
    search_fields = ("nombre", "rut", "email", "telefono")


class VentanaCotizadaInline(admin.TabularInline):
    model = VentanaCotizada
    extra = 0


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cliente",
        "empresa",
        "empleado",
        "estado",
        "total",
        "fecha_ingreso",
    )
    list_filter = ("estado", "empresa")
    search_fields = ("cliente__nombre", "comentarios")
    inlines = [VentanaCotizadaInline]


class PerfilSerieInline(admin.TabularInline):
    model = PerfilSerie
    extra = 0


class PrecioSerieInline(admin.TabularInline):
    model = PrecioSerie
    extra = 0


@admin.register(SerieAluminio)
class SerieAluminioAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "empresa")
    list_filter = ("empresa",)
    inlines = [PerfilSerieInline, PrecioSerieInline]


class PrecioPerfilIndividualInline(admin.TabularInline):
    model = PrecioPerfilIndividual
    extra = 0


@admin.register(PerfilIndividual)
class PerfilIndividualAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "empresa", "largo_tira_m")
    list_filter = ("empresa",)
    inlines = [PrecioPerfilIndividualInline]


@admin.register(PlanchaVidrio)
class PlanchaVidrioAdmin(admin.ModelAdmin):
    list_display = ("tipo_vidrio", "empresa", "ancho_plancha_m", "alto_plancha_m", "precio")
    list_filter = ("empresa",)


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "empresa", "precio_paquete", "cantidad_paquete")
    list_filter = ("empresa",)
