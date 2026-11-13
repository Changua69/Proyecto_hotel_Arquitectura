"""Errores de persistencia traducidos desde MongoDB.

El servicio (semana 2) los convierte en errores de negocio / códigos HTTP:
  SolapeReservaError         -> 409 SIN_DISPONIBILIDAD (o reintento con otra habitación)
  ReferenciaInexistenteError -> 404 NO_ENCONTRADO
  DatosInvalidosError        -> 400 FECHAS_INVALIDAS / datos inválidos
"""


class PersistenciaError(Exception):
    """Error base de la capa de persistencia."""


class SolapeReservaError(PersistenciaError):
    """El índice único de noches ocupadas rechazó una reserva solapada (RN-01)."""


class ReferenciaInexistenteError(PersistenciaError):
    """Huésped o habitación inexistente (RN-05). MongoDB no tiene claves foráneas:
    el repositorio lo verifica dentro de la misma transacción."""


class DatosInvalidosError(PersistenciaError):
    """El validador de la colección rechazó el documento (p. ej. salida <= entrada, RN-03)."""
