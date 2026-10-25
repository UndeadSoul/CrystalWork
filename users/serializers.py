"""Gestion de usuarios (jefe y administrador) y de empresas (administrador).

Reglas de acceso (ver tambien users/views.py):
  - Jefe: solo operarios de su empresa; el rol y la empresa los fija el servidor.
  - Administrador: usuarios de cualquier empresa (jefes y operarios) y empresas.
  - Nadie crea administradores del sistema desde la API.
  - La empresa de un usuario no cambia despues de crearlo (su historial
    pertenece a esa empresa).
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from core import validacion as val
from core.rut import formatear_rut

from .models import Empresa, Usuario


def _validar(valor, validators):
    """Ejecuta validators de Django y los convierte a errores de DRF."""
    try:
        for v in validators:
            v(valor)
    except DjangoValidationError as e:
        raise serializers.ValidationError(e.messages)
    return valor


class UsuarioGestionSerializer(serializers.ModelSerializer):
    rol_display = serializers.CharField(source="get_rol_display", read_only=True)
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        style={"input_type": "password"},
        help_text="Obligatoria al crear. Para cambiarla despues: accion 'clave'.",
    )

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "telefono",
            "rol",
            "rol_display",
            "empresa",
            "empresa_nombre",
            "is_active",
            "last_login",
            "date_joined",
            "password",
        ]
        read_only_fields = ["id", "is_active", "last_login", "date_joined"]
        extra_kwargs = {
            **val.mensajes("username", "telefono"),
            "first_name": {
                "required": True,
                "allow_blank": False,
                "error_messages": val.MENSAJES_DRF["first_name"],
            },
            "last_name": {
                "required": True,
                "allow_blank": False,
                "error_messages": val.MENSAJES_DRF["last_name"],
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Usuario: unicidad + reglas propias (validate_username) en lugar del
        # validador generico de Django.
        self.fields["username"].validators = [
            UniqueValidator(
                queryset=Usuario.objects.all(),
                message="Ya existe un usuario con ese nombre de usuario.",
            )
        ]
        # Lo que el actor no puede elegir no se valida: lo fija el servidor.
        actor = self.context.get("request") and self.context["request"].user
        if actor and not actor.is_superuser:
            self.fields["empresa"].read_only = True
            self.fields["rol"].read_only = True
        elif self.instance is not None:
            self.fields["empresa"].read_only = True

    @property
    def _actor(self):
        return self.context["request"].user

    def validate_username(self, valor):
        return _validar(valor, val.validar_username)

    def validate_first_name(self, valor):
        return val.normalizar_espacios(valor)

    def validate_last_name(self, valor):
        return val.normalizar_espacios(valor)

    def validate_email(self, valor):
        return _validar(valor, val.validar_email) if valor else valor

    def validate_telefono(self, valor):
        return val.normalizar_espacios(valor)

    def validate(self, attrs):
        actor = self._actor
        creando = self.instance is None
        errores = {}

        if actor.is_superuser:
            # Al editar, la empresa es de solo lectura (ver __init__): el
            # historial del usuario pertenece a esa empresa.
            if creando:
                if not attrs.get("empresa"):
                    errores["empresa"] = "Selecciona la empresa."
                if not attrs.get("rol"):
                    errores["rol"] = "Selecciona el rol."
        elif creando:
            # Jefe: solo operarios de su propia empresa.
            attrs["empresa"] = actor.empresa
            attrs["rol"] = Usuario.Rol.OPERARIO

        if creando:
            if not attrs.get("password"):
                errores["password"] = "La contraseña es obligatoria."
        else:
            attrs.pop("password", None)

        if errores:
            raise serializers.ValidationError(errores)

        if creando:
            candidato = Usuario(
                **{k: v for k, v in attrs.items() if k != "password"}
            )
            try:
                validate_password(attrs["password"], candidato)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"password": e.messages})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()
        return usuario


class CambioClaveSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True,
        error_messages={"blank": "La contraseña es obligatoria."},
    )

    def validate_password(self, valor):
        try:
            validate_password(valor, self.context["usuario"])
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return valor


class EmpresaSerializer(serializers.ModelSerializer):
    n_usuarios = serializers.IntegerField(read_only=True)

    class Meta:
        model = Empresa
        fields = [
            "id",
            "nombre",
            "rut",
            "direccion",
            "telefono",
            "email",
            "activa",
            "creada_en",
            "n_usuarios",
        ]
        read_only_fields = ["id", "activa", "creada_en", "n_usuarios"]
        extra_kwargs = {
            **val.mensajes("nombre", "direccion", "telefono"),
            "nombre": {
                "error_messages": {
                    **val.MENSAJES_DRF["nombre"],
                    "blank": "El nombre de la empresa es obligatorio.",
                }
            },
        }

    def validate_nombre(self, valor):
        return val.normalizar_espacios(valor)

    def validate_direccion(self, valor):
        return val.normalizar_espacios(valor)

    def validate_telefono(self, valor):
        return val.normalizar_espacios(valor)

    def validate_rut(self, valor):
        if not valor:
            return valor
        rut = formatear_rut(valor)
        qs = Empresa.objects.filter(rut=rut)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una empresa con este RUT.")
        return rut
