from django.contrib import admin

from .models import Proyecto


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "empresa", "estado_produccion", "fecha_creacion")
    list_filter = ("estado_produccion", "empresa")
    search_fields = ("cliente__nombre",)
