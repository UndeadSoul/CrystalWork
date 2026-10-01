from django.contrib import admin

from .models import Cliente, Cotizacion, VentanaCotizada


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
