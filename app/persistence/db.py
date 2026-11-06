"""Gestión de conexiones y transacciones.

Decisión de la semana 13:
- Quien abre la unidad de trabajo (el servicio de aplicación en la semana 2)
  es quien confirma o revierte la transacción.
- `unidad_de_trabajo()` confirma (COMMIT) si el bloque termina sin error,
  revierte (ROLLBACK) si se lanza una excepción y SIEMPRE cierra la conexión.
- Los repositorios reciben la conexión abierta; no hacen commit ni rollback.
"""
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from app.persistence.config import database_url


def nueva_conexion(url: str | None = None) -> psycopg.Connection:
    """Abre una conexión nueva (filas como diccionarios)."""
    return psycopg.connect(url or database_url(), row_factory=dict_row)


@contextmanager
def unidad_de_trabajo(url: str | None = None) -> Iterator[psycopg.Connection]:
    """Transacción delimitada: commit al salir, rollback ante excepción, cierre garantizado."""
    conn = nueva_conexion(url)
    try:
        # Transacción EXTERNA explícita: así los `conn.transaction()` internos de los
        # repositorios son SAVEPOINT y no confirman por su cuenta (hallazgo de la prueba RNF-03).
        with conn.transaction():
            yield conn
    finally:
        conn.close()
