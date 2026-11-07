"""Gestión de conexiones y transacciones (MongoDB).

Decisión de la semana 13:
- Quien abre la unidad de trabajo (el servicio de aplicación en la semana 2)
  es quien confirma o revierte la transacción.
- `unidad_de_trabajo()` abre una sesión con transacción: confirma (commit) si el bloque
  termina sin error, la aborta si se lanza una excepción y SIEMPRE cierra la sesión.
- `en_transaccion(fn)` hace lo mismo, pero además REINTENTA la transacción completa ante
  errores transitorios (conflictos de escritura entre solicitudes simultáneas, RNF-08).
  Es la forma recomendada para escribir reservas.
- Los repositorios reciben la unidad de trabajo abierta; no confirman ni abortan.

MongoDB solo admite transacciones en un replica set (basta uno de un solo nodo; ver README).
"""
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator, TypeVar

from pymongo import MongoClient
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from app.persistence.config import mongo_uri, nombre_base
from app.persistence.errors import PersistenciaError

T = TypeVar("T")

_cliente: MongoClient | None = None
_OPCIONES_TXN = dict(read_concern=ReadConcern("snapshot"), write_concern=WriteConcern("majority"))


@dataclass
class UnidadDeTrabajo:
    """Lo que reciben los repositorios: la base y la sesión con la transacción abierta.
    `sesion` es None cuando se lee fuera de una transacción (p. ej. desde una conexión nueva)."""

    db: Database
    sesion: ClientSession | None = None
    _cliente_propio: MongoClient | None = None

    def cerrar(self) -> None:
        if self._cliente_propio is not None:
            self._cliente_propio.close()


def _crear_cliente(uri: str | None = None) -> MongoClient:
    cliente = MongoClient(uri or mongo_uri(), serverSelectionTimeoutMS=5000, tz_aware=False)
    if "setName" not in cliente.admin.command("hello"):
        cliente.close()
        raise PersistenciaError(
            "MongoDB no está en modo replica set y no admite transacciones. "
            "Inicie mongod con --replSet rs0 y ejecute rs.initiate() (ver README_SEMANA13.md, sección 4)."
        )
    return cliente


def cliente() -> MongoClient:
    """Cliente compartido (MongoClient ya mantiene su propio pool de conexiones)."""
    global _cliente
    if _cliente is None:
        _cliente = _crear_cliente()
    return _cliente


def base() -> Database:
    return cliente()[nombre_base()]


def nueva_conexion(uri: str | None = None) -> UnidadDeTrabajo:
    """Abre un cliente NUEVO, independiente del compartido, sin transacción.
    Sirve para comprobar que lo guardado quedó realmente persistido. Llamar a `cerrar()`."""
    c = _crear_cliente(uri)
    return UnidadDeTrabajo(db=c[nombre_base()], sesion=None, _cliente_propio=c)


@contextmanager
def unidad_de_trabajo() -> Iterator[UnidadDeTrabajo]:
    """Transacción delimitada: commit al salir, abort ante excepción, cierre garantizado."""
    with cliente().start_session() as sesion:
        with sesion.start_transaction(**_OPCIONES_TXN):
            # start_transaction como contexto: commit si el bloque termina bien, abort si hay excepción.
            yield UnidadDeTrabajo(db=base(), sesion=sesion)


def en_transaccion(fn: Callable[[UnidadDeTrabajo], T]) -> T:
    """Ejecuta `fn` dentro de una transacción y la reintenta completa ante errores transitorios
    (WriteConflict entre solicitudes simultáneas). Los errores de la capa (p. ej. SolapeReservaError)
    no son transitorios: abortan y se propagan al servicio."""
    with cliente().start_session() as sesion:
        return sesion.with_transaction(lambda s: fn(UnidadDeTrabajo(db=base(), sesion=s)), **_OPCIONES_TXN)
