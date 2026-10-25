from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Length

# Solo reglas (sin modelos): no genera import circular con core.models.
from core import validacion as val

# Permite usar campo__length en las restricciones CHECK.
models.CharField.register_lookup(Length)


def _largo_opcional(campo, minimo, maximo):
    """CHECK: el texto esta vacio o su largo esta en [minimo, maximo]."""
    return Q(**{campo: ""}) | Q(**{f"{campo}__length__range": (minimo, maximo)})


class Empresa(models.Model):
    """
    Tenant del sistema. En primera instancia habra una sola empresa,
    pero todo el dominio cuelga de aqui para dejar abierta la expansion
    a un modelo SaaS multi-empresa.
    """
    nombre = models.CharField(
        max_length=val.EMPRESA_NOMBRE_MAX, validators=val.validar_empresa_nombre
    )
    rut = models.CharField(
        max_length=val.RUT_MAX,
        blank=True,
        validators=[val.validar_rut],
        help_text="Formato 12.345.678-9. Opcional; unico entre empresas.",
    )
    direccion = models.CharField(
        max_length=val.DIRECCION_MAX, blank=True, validators=val.validar_direccion
    )
    telefono = models.CharField(
        max_length=val.TELEFONO_MAX, blank=True, validators=[val.validar_telefono]
    )
    email = models.EmailField(
        max_length=val.EMAIL_MAX, blank=True, validators=val.validar_email
    )
    activa = models.BooleanField(
        default=True,
        help_text="Si esta desactivada, sus usuarios no pueden iniciar sesion.",
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    # Configuracion de precios
    margen_ganancia_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[val.validar_margen],
        help_text="Porcentaje de ganancia que se suma al costo. Ej: 30 = 30%.",
    )
    precio_transporte_km = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        validators=[val.validar_transporte_km],
        help_text="Precio por kilometro de transporte (CLP).",
    )
    # Control de concurrencia optimista de la configuracion de precios
    # (margen y transporte) editada desde Precios -> General.
    version_config = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(
                condition=Q(margen_ganancia_pct__range=(0, val.MARGEN_MAX)),
                name="empresa_margen_rango",
            ),
            models.CheckConstraint(
                condition=Q(precio_transporte_km__range=(0, val.TRANSPORTE_KM_MAX)),
                name="empresa_transporte_km_rango",
            ),
            models.CheckConstraint(
                condition=Q(
                    nombre__length__range=(
                        val.EMPRESA_NOMBRE_MIN,
                        val.EMPRESA_NOMBRE_MAX,
                    )
                ),
                name="empresa_nombre_largo",
            ),
            models.UniqueConstraint(
                fields=["rut"],
                condition=~Q(rut=""),
                name="empresa_rut_unico",
                violation_error_message="Ya existe una empresa con este RUT.",
            ),
            models.CheckConstraint(
                condition=_largo_opcional("rut", 9, val.RUT_MAX),
                name="empresa_rut_largo",
            ),
            models.CheckConstraint(
                condition=_largo_opcional(
                    "direccion", val.DIRECCION_MIN, val.DIRECCION_MAX
                ),
                name="empresa_direccion_largo",
            ),
            models.CheckConstraint(
                condition=_largo_opcional(
                    "telefono", val.TELEFONO_DIGITOS_MIN, val.TELEFONO_MAX
                ),
                name="empresa_telefono_largo",
            ),
        ]

    def __str__(self):
        return self.nombre


# A nivel de modulo para poder usarlo en el Meta (CHECK); Usuario.Rol es un alias.
class RolUsuario(models.TextChoices):
    JEFE = "JEFE", "Jefe"
    OPERARIO = "OPERARIO", "Operario"


class Usuario(AbstractUser):
    """
    Usuario propio del sistema.

    Niveles de acceso:
      - Administrador del sistema (dueno del SaaS): is_superuser / is_staff,
        sin empresa asignada. Gestiona empresas y usuarios de todas ellas.
      - Jefe: gestiona su empresa y a sus operarios, aprueba cotizaciones.
      - Operario: ingresa cotizaciones y gestiona clientes de su empresa.

    Los usuarios no se eliminan: se desactivan (is_active=False) para conservar
    su historial (cotizaciones, registro de cambios).
    """

    Rol = RolUsuario

    first_name = models.CharField(
        "nombre",
        max_length=val.PERSONA_MAX,
        blank=True,
        validators=val.validar_persona,
    )
    last_name = models.CharField(
        "apellido",
        max_length=val.PERSONA_MAX,
        blank=True,
        validators=val.validar_persona,
    )
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
        choices=RolUsuario.choices,
        null=True,
        blank=True,
        help_text="Vacio para el administrador del sistema.",
    )
    telefono = models.CharField(
        max_length=val.TELEFONO_MAX, blank=True, validators=[val.validar_telefono]
    )

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
        constraints = [
            # Todo usuario que no es administrador del sistema pertenece a una
            # empresa y tiene un rol valido.
            models.CheckConstraint(
                condition=Q(is_superuser=True)
                | Q(empresa__isnull=False, rol__in=RolUsuario.values),
                name="usuario_empresa_y_rol",
            ),
            models.CheckConstraint(
                condition=_largo_opcional(
                    "first_name", val.PERSONA_MIN, val.PERSONA_MAX
                ),
                name="usuario_nombre_largo",
            ),
            models.CheckConstraint(
                condition=_largo_opcional(
                    "last_name", val.PERSONA_MIN, val.PERSONA_MAX
                ),
                name="usuario_apellido_largo",
            ),
            models.CheckConstraint(
                condition=_largo_opcional(
                    "telefono", val.TELEFONO_DIGITOS_MIN, val.TELEFONO_MAX
                ),
                name="usuario_telefono_largo",
            ),
        ]

    @property
    def es_jefe(self):
        return self.rol == self.Rol.JEFE

    @property
    def es_operario(self):
        return self.rol == self.Rol.OPERARIO

    def __str__(self):
        etiqueta = self.get_rol_display() if self.rol else "Administrador"
        return f"{self.username} ({etiqueta})"
