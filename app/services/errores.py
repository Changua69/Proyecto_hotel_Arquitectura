"""Errores de negocio del corte vertical (semana 14).

Cada error lleva el código interno y el HTTP acordados en el documento del segundo corte
(tabla 8 y tabla 15). La API los traduce sin conocer las reglas.
"""


class ErrorNegocio(Exception):
    http: int = 400
    codigo: str = "ERROR_NEGOCIO"

    def __init__(self, mensaje: str, campo: str | None = None, errores: list[dict] | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.campo = campo        # campo del formulario que causó el error (la pantalla lo marca)
        self.errores = errores    # lista [{"campo", "mensaje"}] cuando hay varios errores de validación


class EntradaInvalidaError(ErrorNegocio):
    """Dato de entrada con formato o valor inválido (p. ej. id no positivo)."""

    http = 400
    codigo = "DATOS_INVALIDOS"


class FechasInvalidasError(ErrorNegocio):
    """RN-03 (salida no posterior a la entrada) y RN-04 (entrada en el pasado)."""

    http = 400
    codigo = "FECHAS_INVALIDAS"


class NoEncontradoError(ErrorNegocio):
    """RN-05: huésped o tipo inexistente; también reserva consultada que no existe."""

    http = 404
    codigo = "NO_ENCONTRADO"


class SinDisponibilidadError(ErrorNegocio):
    """RN-01: no queda ninguna habitación libre del tipo en el rango."""

    http = 409
    codigo = "SIN_DISPONIBILIDAD"


class CapacidadExcedidaError(ErrorNegocio):
    """RN-02: el número de personas supera la capacidad del tipo."""

    http = 422
    codigo = "CAPACIDAD_EXCEDIDA"


# ------------------------------------------------------------------ semana 15
class DatoDuplicadoError(ErrorNegocio):
    """Documento o correo de huésped que ya pertenece a otro huésped."""

    http = 409
    codigo = "DATO_DUPLICADO"


class HuespedConReservasError(ErrorNegocio):
    """No se borra un huésped que tiene reservas activas (CONFIRMADA o EN_CURSO)."""

    http = 409
    codigo = "HUESPED_CON_RESERVAS"


class NoAutenticadoError(ErrorNegocio):
    """Falta el token o está vencido: hay que iniciar sesión."""

    http = 401
    codigo = "NO_AUTENTICADO"


class SinPermisoError(ErrorNegocio):
    """El usuario inició sesión, pero su rol no permite esta operación."""

    http = 403
    codigo = "SIN_PERMISO"
