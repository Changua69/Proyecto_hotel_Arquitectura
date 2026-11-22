"""Esquemas JSON de la API del corte (contratos de la semana 14).

Convenciones: nombres en snake_case, identificadores enteros, fechas AAAA-MM-DD,
dinero como número en pesos colombianos. Los esquemas aparecen en /docs.
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.services.reservas import Disponibilidad, ReservaDetalle


def dinero(valor: Decimal) -> int | float:
    """200000.00 -> 200000; conserva decimales si los hay."""
    return int(valor) if valor == valor.to_integral_value() else float(valor)


# ------------------------------------------------------------------ entrada
class ReservaEntrada(BaseModel):
    """Cuerpo de POST /api/reservas. El id, la habitación, el total y el estado los define el backend."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "id_huesped": 1,
                "id_tipo": 2,
                "fecha_entrada": "2026-12-20",
                "fecha_salida": "2026-12-23",
                "numero_personas": 3,
            }
        },
    )

    id_huesped: int = Field(gt=0, description="Id del huésped existente")
    id_tipo: int = Field(gt=0, description="1 Estándar, 2 Familiar, 3 Suite")
    fecha_entrada: date = Field(description="AAAA-MM-DD; no anterior a hoy")
    fecha_salida: date = Field(description="AAAA-MM-DD; posterior a la entrada (no cuenta como noche)")
    numero_personas: int = Field(ge=1, description="No puede superar la capacidad del tipo")


# ------------------------------------------------------------------ salida
class HabitacionLibre(BaseModel):
    id_habitacion: int
    numero: str


class DisponibilidadSalida(BaseModel):
    id_tipo: int
    tipo: str
    capacidad: int
    tarifa_noche: int | float
    fecha_entrada: date
    fecha_salida: date
    noches: int
    personas: int
    habitaciones_disponibles: list[HabitacionLibre]

    @classmethod
    def desde(cls, d: Disponibilidad) -> "DisponibilidadSalida":
        return cls(
            id_tipo=d.tipo.id_tipo,
            tipo=d.tipo.nombre,
            capacidad=d.tipo.capacidad_max,
            tarifa_noche=dinero(d.tipo.tarifa_noche),
            fecha_entrada=d.fecha_entrada,
            fecha_salida=d.fecha_salida,
            noches=d.noches,
            personas=d.personas,
            habitaciones_disponibles=[HabitacionLibre(id_habitacion=h.id_habitacion, numero=h.numero) for h in d.habitaciones],
        )


class HuespedResumen(BaseModel):
    id_huesped: int
    nombre: str


class HabitacionAsignada(BaseModel):
    id_habitacion: int
    numero: str
    tipo: str


class ReservaSalida(BaseModel):
    id_reserva: int
    estado: str
    huesped: HuespedResumen
    habitacion: HabitacionAsignada
    fecha_entrada: date
    fecha_salida: date
    noches: int
    numero_personas: int
    tarifa_noche: int | float
    total: int | float

    @classmethod
    def desde(cls, d: ReservaDetalle) -> "ReservaSalida":
        r = d.reserva
        return cls(
            id_reserva=r.id_reserva,
            estado=r.estado,
            huesped=HuespedResumen(id_huesped=d.huesped.id_huesped, nombre=d.huesped.nombre),
            habitacion=HabitacionAsignada(
                id_habitacion=d.habitacion.id_habitacion, numero=d.habitacion.numero, tipo=d.tipo.nombre
            ),
            fecha_entrada=r.fecha_entrada,
            fecha_salida=r.fecha_salida,
            noches=d.noches,
            numero_personas=r.numero_personas,
            tarifa_noche=dinero(r.tarifa_noche),
            total=dinero(r.total),
        )


class ErrorSalida(BaseModel):
    """Formato de todos los errores controlados."""

    detail: str = Field(description="Mensaje para el usuario")
    codigo: str = Field(description="Código interno: DATOS_INVALIDOS, FECHAS_INVALIDAS, NO_ENCONTRADO, ...")
    campo: str | None = Field(default=None, description="Campo del formulario que causó el error (si aplica)")
    errores: list[dict] | None = Field(default=None, description="[{campo, mensaje}] en errores de validación")


# ------------------------------------------------------------------ huéspedes (semana 15)
class HuespedEntrada(BaseModel):
    """Cuerpo de POST /api/huespedes y PUT /api/huespedes/{id}. El id lo asigna el backend."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "nombre": "María Gómez",
                "documento": "1033445566",
                "nacionalidad": "Colombiana",
                "telefono": "3104567890",
                "correo": "maria@example.com",
            }
        },
    )

    nombre: str = Field(max_length=200, description="2 a 100 caracteres")
    documento: str = Field(max_length=60, description="3 a 30 letras, números, puntos o guiones; único")
    nacionalidad: str | None = Field(default=None, max_length=100)
    telefono: str | None = Field(default=None, max_length=40, description="7 a 20 dígitos; '+' opcional")
    correo: str | None = Field(default=None, max_length=200, description="Único; se guarda en minúsculas")


class HuespedSalida(BaseModel):
    id_huesped: int
    nombre: str
    documento: str
    nacionalidad: str | None
    telefono: str | None
    correo: str | None

    @classmethod
    def desde(cls, h) -> "HuespedSalida":
        return cls(id_huesped=h.id_huesped, nombre=h.nombre, documento=h.documento,
                   nacionalidad=h.nacionalidad, telefono=h.telefono, correo=h.correo)
