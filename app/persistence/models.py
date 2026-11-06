"""Objetos que entran y salen de los repositorios (contrato para la semana 2)."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class TipoHabitacion:
    id_tipo: int
    nombre: str
    capacidad_max: int
    tarifa_noche: Decimal


@dataclass(frozen=True)
class Habitacion:
    id_habitacion: int
    numero: str
    id_tipo: int
    estado: str


@dataclass(frozen=True)
class Huesped:
    id_huesped: int
    nombre: str
    documento: str
    nacionalidad: str | None
    telefono: str | None
    correo: str | None


@dataclass(frozen=True)
class NuevaReserva:
    """Datos que el servicio entrega al repositorio para persistir (sin id)."""
    id_huesped: int
    id_habitacion: int
    fecha_entrada: date
    fecha_salida: date
    numero_personas: int
    tarifa_noche: Decimal
    total: Decimal
    estado: str = "CONFIRMADA"


@dataclass(frozen=True)
class Reserva:
    id_reserva: int
    id_huesped: int
    id_habitacion: int
    fecha_entrada: date
    fecha_salida: date
    numero_personas: int
    tarifa_noche: Decimal
    total: Decimal
    estado: str
    creada_en: datetime
