"""Errores de persistencia traducidos desde PostgreSQL.

El servicio (semana 2) los convierte en errores de negocio / códigos HTTP:
  SolapeReservaError        -> 409 SIN_DISPONIBILIDAD (o reintento con otra habitación)
  ReferenciaInexistenteError -> 404 NO_ENCONTRADO
  DatosInvalidosError       -> 400 FECHAS_INVALIDAS / datos inválidos
"""


class PersistenciaError(Exception):
    """Error base de la capa de persistencia."""


class SolapeReservaError(PersistenciaError):
    """La restricción de exclusión rechazó una reserva solapada (RN-01)."""


class ReferenciaInexistenteError(PersistenciaError):
    """Clave foránea inválida: huésped o habitación inexistente (RN-05)."""


class DatosInvalidosError(PersistenciaError):
    """Una restricción CHECK rechazó los datos (p. ej. salida <= entrada, RN-03)."""
