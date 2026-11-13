"""Contratos de los repositorios (entradas y resultados).

Los servicios de la semana 2 dependen de estos protocolos, no de MongoDB.
Así pueden probarse con repositorios simulados en memoria (RNF-06).
"""
from datetime import date
from typing import Protocol

from app.persistence.models import Habitacion, Huesped, NuevaReserva, Reserva, TipoHabitacion


class TipoHabitacionRepo(Protocol):
    def buscar_por_id(self, id_tipo: int) -> TipoHabitacion | None:
        """RF-02 y RF-04: capacidad y tarifa del tipo. None si no existe."""


class HabitacionRepo(Protocol):
    def obtener_por_id(self, id_habitacion: int) -> Habitacion | None:
        """RF-04: datos de la habitación asignada. None si no existe."""

    def buscar_por_tipo(self, id_tipo: int) -> list[Habitacion]:
        """Todas las habitaciones de un tipo, ordenadas por número."""

    def buscar_libres_por_tipo_y_rango(self, id_tipo: int, entrada: date, salida: date) -> list[Habitacion]:
        """RF-02 y RF-04: habitaciones del tipo sin reservas activas solapadas en [entrada, salida)."""


class HuespedRepo(Protocol):
    def obtener_por_id(self, id_huesped: int) -> Huesped | None:
        """RF-04: el negocio verifica que el huésped exista. None si no existe."""


class ReservaRepo(Protocol):
    def buscar_reservas_solapadas(self, id_habitacion: int, entrada: date, salida: date) -> list[Reserva]:
        """RF-04: hecho con el que negocio decide disponibilidad de una habitación concreta."""

    def guardar(self, reserva: NuevaReserva) -> int:
        """RF-04: persiste y retorna el id real.
        Lanza SolapeReservaError, ReferenciaInexistenteError o DatosInvalidosError."""

    def buscar_por_id(self, id_reserva: int) -> Reserva | None:
        """RF-04 (confirmación): recupera la reserva o None si no existe."""
