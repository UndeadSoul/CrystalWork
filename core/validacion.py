"""Reglas de validacion compartidas (limites y caracteres permitidos).

Se aplican en tres capas:
  - Modelo: validators de cada campo (DRF los usa al validar la API).
  - BD: CheckConstraint / UniqueConstraint en el Meta de cada modelo.
  - Frontend: crystalworkfe/src/utils/validacion.js replica estos valores;
    si se cambia algo aqui, hay que cambiarlo tambien alla.
"""

import re
from decimal import Decimal

from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
    RegexValidator,
)
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

from .rut import rut_valido

# ------------------------------------------------------------------
# Limites
# ------------------------------------------------------------------

NOMBRE_MIN, NOMBRE_MAX = 5, 50
DIRECCION_MIN, DIRECCION_MAX = 5, 100
EMAIL_MAX = 100
RUT_MAX = 12  # "12.345.678-9"
COMENTARIO_MAX = 1000
DISTANCIA_MIN, DISTANCIA_MAX = Decimal("0.1"), Decimal("500")
MONTO_AGREGADO_MAX = 10_000_000
VENTANAS_MAX = 50
DIMENSION_MIN, DIMENSION_MAX = 300, 3000  # mm
CANTIDAD_MIN, CANTIDAD_MAX = 1, 10
TELEFONO_MAX = 20
TELEFONO_DIGITOS_MIN, TELEFONO_DIGITOS_MAX = 8, 12

# Catalogo de precios. En precios y pesos el 0 significa "sin configurar"
# (se avisara en la fase de alertas); cualquier otro valor debe estar en rango.
PRECIO_MAX = 10_000_000
MARGEN_MAX = Decimal("200")
TRANSPORTE_KM_MAX = 50_000
PESO_SERIE_MIN, PESO_SERIE_MAX = Decimal("0.1"), Decimal("100")  # kg
PESO_PERFIL_MIN = Decimal("0.001")  # kg; maximo: el peso total de su serie
LARGO_TIRA_MIN, LARGO_TIRA_MAX = Decimal("1"), Decimal("7")  # m
LARGO_TIRA_ESTANDAR = Decimal("6")
PLANCHA_MIN, PLANCHA_MAX = Decimal("0.5"), Decimal("4")  # m
CANTIDAD_PAQUETE_MIN = Decimal("0.001")

# Pagos de proyectos
PAGO_MAX = 10_000_000  # ademas, no puede superar el saldo pendiente
PAGO_COMENTARIO_MAX = 200
MOTIVO_ANULACION_MIN = 5

# Usuarios y empresas
USERNAME_MIN, USERNAME_MAX = 3, 30
PERSONA_MIN, PERSONA_MAX = 2, 50  # nombre / apellido de un usuario
EMPRESA_NOMBRE_MIN, EMPRESA_NOMBRE_MAX = 3, 100

# ------------------------------------------------------------------
# Caracteres permitidos
# ------------------------------------------------------------------

LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"

# \Z (no $): en Python "$" tambien acepta un salto de linea final.
NOMBRE_RE = rf"^[{LETRAS} ]+\Z"
DIRECCION_RE = rf"^[{LETRAS}0-9 .,#°/\-]+\Z"
COMENTARIO_RE = rf"^[{LETRAS}0-9\s.,:¿?¡!()°#$%+/\-]+\Z"
EMAIL_RE = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\Z"
TELEFONO_RE = r"^\+?[0-9 ]+\Z"
USERNAME_RE = r"^[A-Za-z0-9._\-]+\Z"
EMPRESA_NOMBRE_RE = rf"^[{LETRAS}0-9 .,&\-]+\Z"

# ------------------------------------------------------------------
# Validators
# ------------------------------------------------------------------

validar_nombre = [
    MinLengthValidator(NOMBRE_MIN, f"Debe tener al menos {NOMBRE_MIN} caracteres."),
    MaxLengthValidator(NOMBRE_MAX, f"Debe tener como máximo {NOMBRE_MAX} caracteres."),
    RegexValidator(NOMBRE_RE, "Solo se permiten letras (con tildes y ñ) y espacios."),
]

validar_direccion = [
    MinLengthValidator(DIRECCION_MIN, f"Debe tener al menos {DIRECCION_MIN} caracteres."),
    MaxLengthValidator(DIRECCION_MAX, f"Debe tener como máximo {DIRECCION_MAX} caracteres."),
    RegexValidator(
        DIRECCION_RE,
        "Solo se permiten letras, números, espacios y los signos . , # ° / -",
    ),
]

validar_email = [
    RegexValidator(
        EMAIL_RE,
        # %% porque Django formatea los mensajes con "%".
        "Ingresa un correo válido (solo letras, números y . _ %% + - @).",
    ),
]

validar_comentario = [
    MaxLengthValidator(
        COMENTARIO_MAX, f"Debe tener como máximo {COMENTARIO_MAX} caracteres."
    ),
    RegexValidator(
        COMENTARIO_RE,
        "Solo se permiten letras, números, espacios y los signos . , : ¿ ? ¡ ! ( ) ° # $ %% + / -",
    ),
]


def validar_rut(valor):
    if not rut_valido(valor):
        raise ValidationError("El RUT no es válido.")


validar_distancia = [
    MinValueValidator(DISTANCIA_MIN, f"Debe ser al menos {DISTANCIA_MIN} km."),
    MaxValueValidator(DISTANCIA_MAX, f"Debe ser como máximo {DISTANCIA_MAX} km."),
]

validar_monto_agregado = [
    MinValueValidator(0, "No puede ser negativo."),
    MaxValueValidator(
        MONTO_AGREGADO_MAX, "Debe ser como máximo $10.000.000."
    ),
]

_rango_dimension = f"Debe estar entre {DIMENSION_MIN} y {DIMENSION_MAX} mm."
validar_dimension = [
    MinValueValidator(DIMENSION_MIN, _rango_dimension),
    MaxValueValidator(DIMENSION_MAX, _rango_dimension),
]

_rango_cantidad = f"Debe estar entre {CANTIDAD_MIN} y {CANTIDAD_MAX}."
validar_cantidad = [
    MinValueValidator(CANTIDAD_MIN, _rango_cantidad),
    MaxValueValidator(CANTIDAD_MAX, _rango_cantidad),
]


def validar_telefono(valor):
    if not re.match(TELEFONO_RE, valor or ""):
        raise ValidationError(
            "Solo se permiten números, espacios y un + al inicio (ej: +56 9 1234 5678)."
        )
    digitos = sum(ch.isdigit() for ch in valor)
    if not TELEFONO_DIGITOS_MIN <= digitos <= TELEFONO_DIGITOS_MAX:
        raise ValidationError(
            f"Debe tener entre {TELEFONO_DIGITOS_MIN} y {TELEFONO_DIGITOS_MAX} dígitos."
        )


def _num(valor):
    return f"{valor:,}".replace(",", ".") if isinstance(valor, int) else str(valor)


@deconstructible
class Rango:
    """Valida que el valor este en [minimo, maximo]. Con cero=True tambien
    acepta 0 ("sin configurar")."""

    def __init__(self, minimo, maximo, unidad="", cero=False):
        self.minimo, self.maximo, self.unidad, self.cero = minimo, maximo, unidad, cero

    @property
    def mensaje(self):
        u = f" {self.unidad}" if self.unidad else ""
        texto = f"Debe estar entre {_num(self.minimo)} y {_num(self.maximo)}{u}"
        return texto + (" (o 0 si aún no se configura)." if self.cero else ".")

    def __call__(self, valor):
        if valor is None or (self.cero and valor == 0):
            return
        if not self.minimo <= valor <= self.maximo:
            raise ValidationError(self.mensaje)

    def __eq__(self, otro):
        return isinstance(otro, Rango) and vars(self) == vars(otro)


# Validators del catalogo.
validar_precio = Rango(0, PRECIO_MAX, "CLP")
validar_margen = Rango(0, MARGEN_MAX, "%")
validar_transporte_km = Rango(0, TRANSPORTE_KM_MAX, "CLP")
validar_peso_serie = Rango(PESO_SERIE_MIN, PESO_SERIE_MAX, "kg", cero=True)
validar_peso_perfil = Rango(PESO_PERFIL_MIN, PESO_SERIE_MAX, "kg", cero=True)
validar_largo_tira = Rango(LARGO_TIRA_MIN, LARGO_TIRA_MAX, "m")
validar_plancha = Rango(PLANCHA_MIN, PLANCHA_MAX, "m")


validar_monto_pago = Rango(1, PAGO_MAX, "CLP")

validar_comentario_pago = [
    MaxLengthValidator(
        PAGO_COMENTARIO_MAX, f"Debe tener como máximo {PAGO_COMENTARIO_MAX} caracteres."
    ),
    RegexValidator(
        COMENTARIO_RE,
        "Solo se permiten letras, números, espacios y los signos . , : ¿ ? ¡ ! ( ) ° # $ %% + / -",
    ),
]


def validar_cantidad_paquete(valor):
    if valor is not None and valor < CANTIDAD_PAQUETE_MIN:
        raise ValidationError("Debe ser mayor que 0.")


def _validar_largo(minimo, maximo):
    return [
        MinLengthValidator(minimo, f"Debe tener al menos {minimo} caracteres."),
        MaxLengthValidator(maximo, f"Debe tener como máximo {maximo} caracteres."),
    ]


validar_username = _validar_largo(USERNAME_MIN, USERNAME_MAX) + [
    RegexValidator(
        USERNAME_RE,
        "Solo letras sin tildes, números y los signos . _ - (sin espacios).",
    ),
]

validar_persona = _validar_largo(PERSONA_MIN, PERSONA_MAX) + [
    RegexValidator(NOMBRE_RE, "Solo se permiten letras (con tildes y ñ) y espacios."),
]

validar_empresa_nombre = _validar_largo(EMPRESA_NOMBRE_MIN, EMPRESA_NOMBRE_MAX) + [
    RegexValidator(
        EMPRESA_NOMBRE_RE,
        "Solo se permiten letras, números, espacios y los signos . , & -",
    ),
]


# DRF convierte los validators de largo y rango del modelo en sus propios
# argumentos (min_length, max_value, ...) con mensajes genericos; estos los
# reemplazan en los serializers (extra_kwargs) para mantener un formato comun.
_largo = {
    "min_length": "Debe tener al menos {min_length} caracteres.",
    "max_length": "Debe tener como máximo {max_length} caracteres.",
}
_entero = {"invalid": "Ingresa un número entero.", "max_decimal_places": "Ingresa un número entero."}

MENSAJES_DRF = {
    "nombre": {**_largo, "blank": "El nombre es obligatorio."},
    "rut": {"blank": "El RUT es obligatorio.", "required": "El RUT es obligatorio."},
    "direccion": _largo,
    "direccion_entrega": _largo,
    "comentarios": _largo,
    "username": {**_largo, "blank": "El nombre de usuario es obligatorio."},
    "first_name": {**_largo, "blank": "El nombre es obligatorio."},
    "last_name": {**_largo, "blank": "El apellido es obligatorio."},
    "distancia_transporte_km": {
        "invalid": "Ingresa un número.",
        "min_value": f"Debe ser al menos {DISTANCIA_MIN} km.",
        "max_value": f"Debe ser como máximo {DISTANCIA_MAX} km.",
        "max_decimal_places": "Usa como máximo 1 decimal.",
        "max_digits": f"Debe ser como máximo {DISTANCIA_MAX} km.",
        "max_whole_digits": f"Debe ser como máximo {DISTANCIA_MAX} km.",
    },
    "monto_agregado": {
        **_entero,
        "min_value": "No puede ser negativo.",
        "max_value": "Debe ser como máximo $10.000.000.",
        "max_digits": "Debe ser como máximo $10.000.000.",
        "max_whole_digits": "Debe ser como máximo $10.000.000.",
    },
    "ancho_mm": {**_entero, "min_value": _rango_dimension, "max_value": _rango_dimension},
    "alto_mm": {**_entero, "min_value": _rango_dimension, "max_value": _rango_dimension},
    "cantidad": {**_entero, "min_value": _rango_cantidad, "max_value": _rango_cantidad},
}


def _decimal(decimales, fuera_de_rango):
    return {
        "invalid": "Ingresa un número.",
        "max_decimal_places": f"Usa como máximo {decimales} decimales.",
        "max_digits": fuera_de_rango,
        "max_whole_digits": fuera_de_rango,
    }


def _monto(fuera_de_rango):
    return {**_entero, "max_digits": fuera_de_rango, "max_whole_digits": fuera_de_rango}


MENSAJES_DRF.update(
    {
        "telefono": {"max_length": "Debe tener como máximo {max_length} caracteres."},
        "precio": _monto(validar_precio.mensaje),
        "precio_paquete": _monto(validar_precio.mensaje),
        "precio_transporte_km": _monto(validar_transporte_km.mensaje),
        "margen_ganancia_pct": _decimal(2, validar_margen.mensaje),
        "peso_total_kg": _decimal(3, validar_peso_serie.mensaje),
        "peso_kg": _decimal(3, validar_peso_perfil.mensaje),
        "largo_tira_m": _decimal(3, validar_largo_tira.mensaje),
        "ancho_plancha_m": _decimal(3, validar_plancha.mensaje),
        "alto_plancha_m": _decimal(3, validar_plancha.mensaje),
        "cantidad_paquete": _decimal(3, "Valor demasiado grande."),
        "monto_abonado": {**_monto("Valor demasiado grande."), "min_value": "No puede ser negativo."},
        "monto": {**_monto(validar_monto_pago.mensaje), "required": "Ingresa el monto."},
        "fecha": {
            "invalid": "Ingresa una fecha válida.",
            "required": "Ingresa la fecha del pago.",
            "null": "Ingresa la fecha del pago.",
        },
        "comentario": _largo,
    }
)


def mensajes(*campos):
    """extra_kwargs para un serializer con los mensajes de los campos dados."""
    return {c: {"error_messages": MENSAJES_DRF[c]} for c in campos}


def normalizar_espacios(valor):
    """Quita espacios repetidos y en los extremos."""
    return " ".join((valor or "").split())
