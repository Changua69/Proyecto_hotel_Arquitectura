"""Repositorios PostgreSQL del corte vertical.

Reglas de la capa:
- Aquí (y en /db) está TODO el SQL del sistema. Servicios, endpoints y pantallas no contienen SQL.
- Los repositorios consultan y guardan; NO deciden reglas de negocio (eso es de la semana 2).
- No hacen commit/rollback: la transacción la controla `unidad_de_trabajo()`.
"""
from datetime import date

import psycopg
from psycopg import errors as pg_errors

from app.persistence.errors import (
    DatosInvalidosError,
    ReferenciaInexistenteError,
    SolapeReservaError,
)
from app.persistence.models import Habitacion, Huesped, NuevaReserva, Reserva, TipoHabitacion

_ESTADOS_ACTIVOS = ("CONFIRMADA", "EN_CURSO")


class PgTipoHabitacionRepository:
    def __init__(self, conn: psycopg.Connection):
        self._conn = conn

    def buscar_por_id(self, id_tipo: int) -> TipoHabitacion | None:
        row = self._conn.execute(
            "SELECT id_tipo, nombre, capacidad_max, tarifa_noche FROM tipo_habitacion WHERE id_tipo = %s",
            (id_tipo,),
        ).fetchone()
        return TipoHabitacion(**row) if row else None


class PgHabitacionRepository:
    def __init__(self, conn: psycopg.Connection):
        self._conn = conn

    def obtener_por_id(self, id_habitacion: int) -> Habitacion | None:
        row = self._conn.execute(
            "SELECT id_habitacion, numero, id_tipo, estado FROM habitacion WHERE id_habitacion = %s",
            (id_habitacion,),
        ).fetchone()
        return Habitacion(**row) if row else None

    def buscar_por_tipo(self, id_tipo: int) -> list[Habitacion]:
        rows = self._conn.execute(
            "SELECT id_habitacion, numero, id_tipo, estado FROM habitacion WHERE id_tipo = %s ORDER BY numero",
            (id_tipo,),
        ).fetchall()
        return [Habitacion(**r) for r in rows]

    def buscar_libres_por_tipo_y_rango(self, id_tipo: int, entrada: date, salida: date) -> list[Habitacion]:
        # Solape de [e1,s1) y [e2,s2) <=> e1 < s2 AND s1 > e2 (la salida no cuenta como noche).
        rows = self._conn.execute(
            """
            SELECT h.id_habitacion, h.numero, h.id_tipo, h.estado
            FROM habitacion h
            WHERE h.id_tipo = %(tipo)s
              AND NOT EXISTS (
                  SELECT 1 FROM reserva r
                  WHERE r.id_habitacion = h.id_habitacion
                    AND r.estado = ANY(%(activos)s)
                    AND r.fecha_entrada < %(salida)s
                    AND r.fecha_salida  > %(entrada)s)
            ORDER BY h.numero
            """,
            {"tipo": id_tipo, "entrada": entrada, "salida": salida, "activos": list(_ESTADOS_ACTIVOS)},
        ).fetchall()
        return [Habitacion(**r) for r in rows]


class PgHuespedRepository:
    def __init__(self, conn: psycopg.Connection):
        self._conn = conn

    def obtener_por_id(self, id_huesped: int) -> Huesped | None:
        row = self._conn.execute(
            """SELECT id_huesped, nombre, documento, nacionalidad, telefono, correo
               FROM huesped WHERE id_huesped = %s""",
            (id_huesped,),
        ).fetchone()
        return Huesped(**row) if row else None


class PgReservaRepository:
    _COLUMNAS = """id_reserva, id_huesped, id_habitacion, fecha_entrada, fecha_salida,
                   numero_personas, tarifa_noche, total, estado, creada_en"""

    def __init__(self, conn: psycopg.Connection):
        self._conn = conn

    def buscar_reservas_solapadas(self, id_habitacion: int, entrada: date, salida: date) -> list[Reserva]:
        rows = self._conn.execute(
            f"""SELECT {self._COLUMNAS} FROM reserva
                WHERE id_habitacion = %s AND estado = ANY(%s)
                  AND fecha_entrada < %s AND fecha_salida > %s
                ORDER BY fecha_entrada""",
            (id_habitacion, list(_ESTADOS_ACTIVOS), salida, entrada),
        ).fetchall()
        return [Reserva(**r) for r in rows]

    def guardar(self, reserva: NuevaReserva) -> int:
        """Inserta dentro de un SAVEPOINT: si la BD rechaza la fila, la transacción
        externa sigue viva y el servicio puede reintentar con otra habitación."""
        try:
            with self._conn.transaction():  # SAVEPOINT anidado
                row = self._conn.execute(
                    """INSERT INTO reserva (id_huesped, id_habitacion, fecha_entrada, fecha_salida,
                                            numero_personas, tarifa_noche, total, estado)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id_reserva""",
                    (
                        reserva.id_huesped,
                        reserva.id_habitacion,
                        reserva.fecha_entrada,
                        reserva.fecha_salida,
                        reserva.numero_personas,
                        reserva.tarifa_noche,
                        reserva.total,
                        reserva.estado,
                    ),
                ).fetchone()
        except pg_errors.ExclusionViolation as e:
            raise SolapeReservaError("La habitación ya tiene una reserva activa en ese rango") from e
        except pg_errors.ForeignKeyViolation as e:
            raise ReferenciaInexistenteError("Huésped o habitación inexistente") from e
        except pg_errors.CheckViolation as e:
            raise DatosInvalidosError(f"Datos rechazados por la base: {e.diag.constraint_name}") from e
        return row["id_reserva"]

    def buscar_por_id(self, id_reserva: int) -> Reserva | None:
        row = self._conn.execute(
            f"SELECT {self._COLUMNAS} FROM reserva WHERE id_reserva = %s", (id_reserva,)
        ).fetchone()
        return Reserva(**row) if row else None
