"""Contratos de los repositorios (entradas y resultados).

Los servicios de la semana 2 dependen de estos protocolos, no de MongoDB.
Así pueden probarse con repositorios simulados en memoria (RNF-06).
"""
from datetime import date
from typing import Protocol

from app.persistence.models import (
    Habitacion, Huesped, NuevaReserva, NuevoHuesped, Reserva, ReservaFila, TipoHabitacion, Usuario,
)


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

    # --- CRUD de huéspedes (semana 15) ---
    def listar(self, buscar: str | None = None) -> list[Huesped]:
        """Huéspedes ordenados por nombre; `buscar` filtra por nombre, documento o correo."""

    def crear(self, huesped: NuevoHuesped) -> int:
        """Guarda y retorna el id real. Lanza DuplicadoError si el documento o el correo ya existen."""

    def actualizar(self, id_huesped: int, huesped: NuevoHuesped) -> bool:
        """Reemplaza los datos. False si el huésped no existe. Lanza DuplicadoError."""

    def eliminar(self, id_huesped: int) -> bool:
        """Borra el huésped. False si no existía."""

    def contar_reservas_activas(self, id_huesped: int) -> int:
        """Reservas CONFIRMADA o EN_CURSO del huésped (para impedir borrarlo)."""


class ReservaRepo(Protocol):
    def buscar_reservas_solapadas(self, id_habitacion: int, entrada: date, salida: date) -> list[Reserva]:
        """RF-04: hecho con el que negocio decide disponibilidad de una habitación concreta."""

    def guardar(self, reserva: NuevaReserva) -> int:
        """RF-04: persiste y retorna el id real.
        Lanza SolapeReservaError, ReferenciaInexistenteError o DatosInvalidosError."""

    def buscar_por_id(self, id_reserva: int) -> Reserva | None:
        """RF-04 (confirmación): recupera la reserva o None si no existe."""


class GestionRepo(Protocol):
    """Consultas del panel del personal, administración y reportes (semana 15)."""

    def listar_reservas(self, estado: str | None = None, desde: date | None = None,
                        hasta: date | None = None, id_huesped: int | None = None,
                        limite: int = 500) -> list[ReservaFila]:
        """Reservas con fecha de entrada en [desde, hasta], las más recientes primero."""

    def cancelar_reserva(self, id_reserva: int) -> bool:
        """CONFIRMADA -> CANCELADA. False si no estaba CONFIRMADA (o no existe)."""

    def contar(self, coleccion: str, filtro_estado: list[str] | None = None) -> int:
        """Total de documentos de 'huespedes', 'habitaciones' o 'reservas' (opcionalmente por estado)."""

    def ocupadas_en(self, dia: date) -> int:
        """Habitaciones con una reserva activa que incluye la noche de `dia`."""

    def listar_tipos(self) -> list[TipoHabitacion]: ...

    def actualizar_tipo(self, id_tipo: int, capacidad_max: int, tarifa_noche) -> bool: ...


class UsuarioRepo(Protocol):
    def listar(self) -> list[Usuario]: ...

    def obtener(self, email: str) -> Usuario | None: ...

    def crear(self, usuario: Usuario, hash_clave: str) -> None:
        """Lanza DuplicadoError('email') si el correo ya existe."""

    def cambiar_rol(self, email: str, rol: str) -> bool: ...

    def eliminar(self, email: str) -> bool: ...

    def contar_rol(self, rol: str) -> int: ...
