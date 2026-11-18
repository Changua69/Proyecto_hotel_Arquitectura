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
class NuevoHuesped:
    """Datos de un huésped que el servicio entrega al repositorio (sin id). Ya vienen validados."""
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


# ------------------------------------------------------------------ semana 15: gestión y reportes
@dataclass(frozen=True)
class ReservaFila:
    """Reserva con los nombres ya resueltos (huésped, habitación, tipo) para listados y reportes."""
    id_reserva: int
    estado: str
    fecha_entrada: date
    fecha_salida: date
    numero_personas: int
    tarifa_noche: Decimal
    total: Decimal
    id_huesped: int
    huesped: str
    habitacion: str
    tipo: str
    creada_en: datetime

    @property
    def noches(self) -> int:
        return (self.fecha_salida - self.fecha_entrada).days


@dataclass(frozen=True)
class Usuario:
    """Cuenta de acceso (colección users de la base de la aplicación). Nunca incluye la contraseña."""
    email: str
    nombre: str
    rol: str
