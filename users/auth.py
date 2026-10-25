"""Autenticacion JWT que ademas exige que la empresa del usuario este activa.

Los usuarios desactivados (is_active=False) ya los rechaza SimpleJWT; aqui se
agrega el bloqueo por empresa desactivada en cada peticion (asi una sesion
abierta deja de funcionar al desactivarla). El bloqueo al iniciar sesion esta
en users/views.py (TokenEmpresaActivaView).

Este modulo no debe importar vistas (DRF lo carga desde la configuracion y se
produciria un import circular).
"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

def empresa_inactiva(user):
    return user.empresa_id is not None and not user.empresa.activa


def error_empresa_inactiva():
    # El "code" va en el cuerpo para que el frontend muestre este motivo
    # (y no "usuario o contraseña incorrectos").
    return AuthenticationFailed(
        {
            "detail": "Tu empresa está desactivada. Contacta al administrador.",
            "code": "empresa_inactiva",
        }
    )


class JWTEmpresaActivaAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if empresa_inactiva(user):
            raise error_empresa_inactiva()
        return user
