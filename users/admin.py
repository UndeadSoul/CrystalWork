from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Empresa, Usuario


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rut", "activa", "creada_en")
    search_fields = ("nombre", "rut")
    list_filter = ("activa",)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "email", "empresa", "rol", "is_staff")
    list_filter = ("rol", "empresa", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")

    fieldsets = UserAdmin.fieldsets + (
        (_("CrystalWork"), {"fields": ("empresa", "rol", "telefono")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (_("CrystalWork"), {"fields": ("empresa", "rol", "telefono")}),
    )
