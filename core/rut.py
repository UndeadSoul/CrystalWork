"""Validacion de RUT chileno (modulo 11)."""


def limpiar_rut(rut):
    return rut.replace(".", "").replace("-", "").strip().upper()


def digito_verificador(cuerpo):
    suma = 0
    multiplo = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplo
        multiplo = 2 if multiplo == 7 else multiplo + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def rut_valido(rut):
    limpio = limpiar_rut(rut)
    if not 2 <= len(limpio) <= 9:
        return False
    cuerpo, dv = limpio[:-1], limpio[-1]
    if not cuerpo.isdigit():
        return False
    return digito_verificador(cuerpo) == dv


def formatear_rut(rut):
    """Formato canonico "12.345.678-9" (asi se guarda, para que la unicidad
    no dependa de como lo escribio el usuario)."""
    limpio = limpiar_rut(rut)
    cuerpo, dv = limpio[:-1], limpio[-1]
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}"
