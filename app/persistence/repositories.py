"""Repositorios MongoDB del corte vertical.

Reglas de la capa:
- Aquí (y en /db) está TODO el acceso a MongoDB del corte. Servicios, endpoints y pantallas
  no usan pymongo ni colecciones.
- Los repositorios consultan y guardan; NO deciden reglas de negocio (eso es de la semana 2).
- No confirman ni abortan: la transacción la controla `unidad_de_trabajo()` / `en_transaccion()`.
- En la frontera se convierten tipos: date <-> datetime (BSON no tiene fecha sin hora) y
  Decimal <-> Decimal128 (dinero sin errores de punto flotante).
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from bson.decimal128 import Decimal128
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, WriteError

from app.persistence.db import UnidadDeTrabajo
from app.persistence.errors import (
    DatosInvalidosError,
    ReferenciaInexistenteError,
    SolapeReservaError,
)
from app.persistence.models import Habitacion, Huesped, NuevaReserva, Reserva, TipoHabitacion

ESTADOS_ACTIVOS = ["CONFIRMADA", "EN_CURSO"]
_VALIDACION_FALLIDA = 121  # código de MongoDB: DocumentValidationFailure
_CENTAVOS = Decimal("0.01")


# ------------------------------------------------------------------ conversiones de frontera
def a_fecha_bson(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def a_dinero_bson(valor: Decimal | int | float) -> Decimal128:
    return Decimal128(Decimal(str(valor)).quantize(_CENTAVOS))


def noches_de(entrada: date, salida: date) -> list[datetime]:
    """Cada noche ocupada del rango semiabierto [entrada, salida): la salida no cuenta como noche."""
    return [a_fecha_bson(entrada + timedelta(days=i)) for i in range((salida - entrada).days)]


def _dinero(v: Decimal128) -> Decimal:
    return v.to_decimal()


class _Repo:
    def __init__(self, uow: UnidadDeTrabajo):
        self._db = uow.db
        self._s = uow.sesion


# ------------------------------------------------------------------ repositorios
class MongoTipoHabitacionRepository(_Repo):
    def buscar_por_id(self, id_tipo: int) -> TipoHabitacion | None:
        d = self._db.tipos_habitacion.find_one({"_id": id_tipo}, session=self._s)
        if not d:
            return None
        return TipoHabitacion(d["_id"], d["nombre"], d["capacidad_max"], _dinero(d["tarifa_noche"]))


class MongoHabitacionRepository(_Repo):
    @staticmethod
    def _a_modelo(d: dict) -> Habitacion:
        return Habitacion(d["_id"], d["numero"], d["id_tipo"], d["estado"])

    def obtener_por_id(self, id_habitacion: int) -> Habitacion | None:
        d = self._db.habitaciones.find_one({"_id": id_habitacion}, session=self._s)
        return self._a_modelo(d) if d else None

    def buscar_por_tipo(self, id_tipo: int) -> list[Habitacion]:
        cur = self._db.habitaciones.find({"id_tipo": id_tipo}, session=self._s).sort("numero", 1)
        return [self._a_modelo(d) for d in cur]

    def buscar_libres_por_tipo_y_rango(self, id_tipo: int, entrada: date, salida: date) -> list[Habitacion]:
        # Solape de [e1,s1) y [e2,s2) <=> e1 < s2 AND s1 > e2 (la salida no cuenta como noche).
        habitaciones = self.buscar_por_tipo(id_tipo)
        ocupadas = set(
            self._db.reservas.distinct(
                "id_habitacion",
                {
                    "id_habitacion": {"$in": [h.id_habitacion for h in habitaciones]},
                    "estado": {"$in": ESTADOS_ACTIVOS},
                    "fecha_entrada": {"$lt": a_fecha_bson(salida)},
                    "fecha_salida": {"$gt": a_fecha_bson(entrada)},
                },
                session=self._s,
            )
        )
        return [h for h in habitaciones if h.id_habitacion not in ocupadas]


class MongoHuespedRepository(_Repo):
    def obtener_por_id(self, id_huesped: int) -> Huesped | None:
        d = self._db.huespedes.find_one({"_id": id_huesped}, session=self._s)
        if not d:
            return None
        return Huesped(d["_id"], d["nombre"], d["documento"], d.get("nacionalidad"), d.get("telefono"), d.get("correo"))


class MongoReservaRepository(_Repo):
    @staticmethod
    def _a_modelo(d: dict) -> Reserva:
        return Reserva(
            id_reserva=d["_id"],
            id_huesped=d["id_huesped"],
            id_habitacion=d["id_habitacion"],
            fecha_entrada=d["fecha_entrada"].date(),
            fecha_salida=d["fecha_salida"].date(),
            numero_personas=d["numero_personas"],
            tarifa_noche=_dinero(d["tarifa_noche"]),
            total=_dinero(d["total"]),
            estado=d["estado"],
            creada_en=d["creada_en"],
        )

    def buscar_reservas_solapadas(self, id_habitacion: int, entrada: date, salida: date) -> list[Reserva]:
        cur = self._db.reservas.find(
            {
                "id_habitacion": id_habitacion,
                "estado": {"$in": ESTADOS_ACTIVOS},
                "fecha_entrada": {"$lt": a_fecha_bson(salida)},
                "fecha_salida": {"$gt": a_fecha_bson(entrada)},
            },
            session=self._s,
        ).sort("fecha_entrada", 1)
        return [self._a_modelo(d) for d in cur]

    def _siguiente_id(self) -> int:
        """Id entero consecutivo (contrato de la semana 2). Al estar dentro de la transacción,
        si esta se aborta el contador también vuelve atrás."""
        doc = self._db.contadores.find_one_and_update(
            {"_id": "reserva"},
            {"$inc": {"valor": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
            session=self._s,
        )
        return doc["valor"]

    def guardar(self, reserva: NuevaReserva) -> int:
        """Inserta la reserva y retorna su id real.

        - Sustituto de las claves foráneas: verifica huésped y habitación en la misma transacción.
        - El validador de la colección rechaza fechas o valores inválidos (RN-03).
        - El índice único parcial (id_habitacion, noches) rechaza el solape entre reservas activas (RN-01),
          incluso con solicitudes simultáneas (RNF-08).
        En MongoDB un rechazo ABORTA la transacción (no hay SAVEPOINT): para probar otra habitación,
        el servicio abre una transacción nueva."""
        if self._db.huespedes.count_documents({"_id": reserva.id_huesped}, limit=1, session=self._s) == 0:
            raise ReferenciaInexistenteError(f"Huésped {reserva.id_huesped} inexistente")
        if self._db.habitaciones.count_documents({"_id": reserva.id_habitacion}, limit=1, session=self._s) == 0:
            raise ReferenciaInexistenteError(f"Habitación {reserva.id_habitacion} inexistente")

        id_reserva = self._siguiente_id()
        documento = {
            "_id": id_reserva,
            "id_huesped": reserva.id_huesped,
            "id_habitacion": reserva.id_habitacion,
            "fecha_entrada": a_fecha_bson(reserva.fecha_entrada),
            "fecha_salida": a_fecha_bson(reserva.fecha_salida),
            "noches": noches_de(reserva.fecha_entrada, reserva.fecha_salida),
            "numero_personas": reserva.numero_personas,
            "tarifa_noche": a_dinero_bson(reserva.tarifa_noche),
            "total": a_dinero_bson(reserva.total),
            "estado": reserva.estado,
            "creada_en": datetime.now().replace(microsecond=0),
        }
        try:
            self._db.reservas.insert_one(documento, session=self._s)
        except DuplicateKeyError as e:
            raise SolapeReservaError("La habitación ya tiene una reserva activa en ese rango") from e
        except WriteError as e:
            if e.code == _VALIDACION_FALLIDA:
                raise DatosInvalidosError("Datos rechazados por el validador de 'reservas'") from e
            raise
        return id_reserva

    def buscar_por_id(self, id_reserva: int) -> Reserva | None:
        d = self._db.reservas.find_one({"_id": id_reserva}, session=self._s)
        return self._a_modelo(d) if d else None
