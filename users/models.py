from django.contrib.auth.models import AbstractUser
from django.db import models


class Empresa(models.Model):
    """
    Tenant del sistema. En primera instancia habra una sola empresa,
    pero todo el dominio cuelga de aqui para dejar abierta la expansion
    a un modelo SaaS multi-empresa.
    """
    nombre = models.CharField(max_length=150)
    rut = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    # Configuracion de precios
    margen_ganancia_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Porcentaje de ganancia que se suma al costo. Ej: 30 = 30%.",
    )
    precio_transporte_km = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        help_text="Precio por kilometro de transporte (CLP).",
    )

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    """
    Usuario propio del sistema.

    Niveles de acceso:
      - Administrador del sistema (dueno del SaaS): is_superuser / is_staff,
        sin empresa asignada. Crea empresas y sus jefes.
      - Jefe: gestiona su empresa, crea trabajadores y aprueba cotizaciones.
      - Operario: ingresa cotizaciones y gestiona clientes de su empresa.
    """

    class Rol(models.TextChoices):
        JEFE = "JEFE", "Jefe"
        OPERARIO = "OPERARIO", "Operario"

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="usuarios",
        null=True,
        blank=True,
        help_text="Empresa a la que pertenece. Vacio para el administrador del sistema.",
    )
    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        null=True,
        blank=True,
        help_text="Vacio para el administrador del sistema.",
    )
    telefono = models.CharField(max_length=30, blank=True)

    @property
    def es_jefe(self):
        return self.rol == self.Rol.JEFE

    @property
    def es_operario(self):
        return self.rol == self.Rol.OPERARIO

    def __str__(self):
        etiqueta = self.get_rol_display() if self.rol else "Administrador"
        return f"{self.username} ({etiqueta})"
