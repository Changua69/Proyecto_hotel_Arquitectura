"""Proveedor de repositorios para los servicios (semana 14).

Los servicios no conocen MongoDB: reciben un `ProveedorRepositorios` y piden
- `leer(fn)`: ejecutar consultas (sin escrituras), o
- `escribir(fn)`: ejecutar un caso de uso con escrituras dentro de UNA transacción.

`MongoProveedor` es la implementación real. En las pruebas aisladas (RNF-06) se usa un
proveedor en memoria con la misma forma, sin abrir conexiones.

Quién administra la transacción: el servicio decide CUÁNDO escribir; `escribir()` abre la
transacción, confirma si `fn` termina bien, la aborta si `fn` lanza una excepción y reintenta
solo ante errores transitorios de MongoDB (conflictos entre solicitudes simultáneas). La sesión
se cierra siempre al salir; el cliente compartido mantiene su propio pool de conexiones.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator, Protocol, TypeVar

from app.persistence.contracts import HabitacionRepo, HuespedRepo, ReservaRepo, TipoHabitacionRepo
from app.persistence.errors import BaseNoDisponibleError

T = TypeVar("T")


@dataclass(frozen=True)
class Repositorios:
    tipos: TipoHabitacionRepo
    habitaciones: HabitacionRepo
    huespedes: HuespedRepo
    reservas: ReservaRepo


class ProveedorRepositorios(Protocol):
    def leer(self, fn: Callable[[Repositorios], T]) -> T: ...

    def escribir(self, fn: Callable[[Repositorios], T]) -> T: ...


class MongoProveedor:
    """Implementación real sobre MongoDB (replica set)."""

    @staticmethod
    def _repos(uow) -> Repositorios:
        from app.persistence.repositories import (
            MongoHabitacionRepository,
            MongoHuespedRepository,
            MongoReservaRepository,
            MongoTipoHabitacionRepository,
        )

        return Repositorios(
            tipos=MongoTipoHabitacionRepository(uow),
            habitaciones=MongoHabitacionRepository(uow),
            huespedes=MongoHuespedRepository(uow),
            reservas=MongoReservaRepository(uow),
        )

    def leer(self, fn: Callable[[Repositorios], T]) -> T:
        from app.persistence.db import unidad_de_trabajo

        with _traducir_caidas():
            with unidad_de_trabajo() as uow:  # lectura consistente (snapshot); no escribe nada
                return fn(self._repos(uow))

    def escribir(self, fn: Callable[[Repositorios], T]) -> T:
        from app.persistence.db import en_transaccion

        with _traducir_caidas():
            return en_transaccion(lambda uow: fn(self._repos(uow)))


@contextmanager
def _traducir_caidas() -> Iterator[None]:
    """Convierte la pérdida de conexión de pymongo en BaseNoDisponibleError."""
    from pymongo.errors import ConnectionFailure

    try:
        yield
    except ConnectionFailure as e:
        raise BaseNoDisponibleError("No hay conexión con la base de datos") from e


def comprobar_conexion() -> None:
    """Ping a la base; lanza BaseNoDisponibleError si no responde. Lo usa /api/salud."""
    from app.persistence.db import cliente

    with _traducir_caidas():
        cliente().admin.command("ping")
