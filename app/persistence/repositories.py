"""Repositorios MongoDB del corte vertical.

Reglas de la capa:
- Aquí (y en /db) está TODO el acceso a MongoDB del corte. Servicios, endpoints y pantallas
  no usan pymongo ni colecciones.
- Los repositorios consultan y guardan; NO deciden reglas de negocio (eso es de la semana 2).
- No confirman ni abortan: la transacción la controla `unidad_de_trabajo()` / `en_transaccion()`.
- En la frontera se convierten tipos: date <-> datetime (BSON no tiene fecha sin hora) y
  Decimal <-> Decimal128 (dinero sin errores de punto flotante).
"""
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from bson.decimal128 import Decimal128
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, WriteError

from app.persistence.db import UnidadDeTrabajo
from app.persistence.errors import (
    DatosInvalidosError,
    DuplicadoError,
    ReferenciaInexistenteError,
    SolapeReservaError,
)
from app.persistence.models import (
    Habitacion, Huesped, NuevaReserva, NuevoHuesped, Reserva, ReservaFila, TipoHabitacion,
)

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
    _LIMITE_LISTADO = 200

    @staticmethod
    def _a_modelo(d: dict) -> Huesped:
        return Huesped(d["_id"], d["nombre"], d["documento"], d.get("nacionalidad"), d.get("telefono"), d.get("correo"))

    @staticmethod
    def _a_documento(h: NuevoHuesped) -> dict:
        return {"nombre": h.nombre, "documento": h.documento, "nacionalidad": h.nacionalidad,
                "telefono": h.telefono, "correo": h.correo}

    @staticmethod
    def _campo_duplicado(e: DuplicateKeyError) -> str:
        """Lee del error qué índice único falló (documento o correo)."""
        patron = (e.details or {}).get("keyPattern") or {}
        if "correo" in patron or "ux_huesped_correo" in str(e):
            return "correo"
        return "documento"

    def obtener_por_id(self, id_huesped: int) -> Huesped | None:
        d = self._db.huespedes.find_one({"_id": id_huesped}, session=self._s)
        return self._a_modelo(d) if d else None

    def listar(self, buscar: str | None = None) -> list[Huesped]:
        filtro: dict = {}
        if buscar:
            # re.escape: el texto del usuario se busca literal (no se interpreta como expresión regular)
            patron = {"$regex": re.escape(buscar), "$options": "i"}
            filtro = {"$or": [{"nombre": patron}, {"documento": patron}, {"correo": patron}]}
        cursor = (self._db.huespedes.find(filtro, session=self._s)
                  .sort([("nombre", 1), ("_id", 1)]).limit(self._LIMITE_LISTADO))
        return [self._a_modelo(d) for d in cursor]

    def _siguiente_id(self) -> int:
        """Contador 'huesped' en la colección contadores. Si no existe (base antigua), arranca en el id máximo."""
        if self._db.contadores.count_documents({"_id": "huesped"}, limit=1, session=self._s) == 0:
            ultimo = self._db.huespedes.find_one({}, sort=[("_id", -1)], projection={"_id": 1}, session=self._s)
            self._db.contadores.update_one({"_id": "huesped"},
                                           {"$setOnInsert": {"valor": ultimo["_id"] if ultimo else 0}},
                                           upsert=True, session=self._s)
        doc = self._db.contadores.find_one_and_update(
            {"_id": "huesped"}, {"$inc": {"valor": 1}},
            return_document=ReturnDocument.AFTER, session=self._s,
        )
        return doc["valor"]

    def _traducir(self, e: Exception) -> Exception:
        if isinstance(e, DuplicateKeyError):
            return DuplicadoError(self._campo_duplicado(e))
        if isinstance(e, WriteError) and e.code == _VALIDACION_FALLIDA:
            return DatosInvalidosError("Datos rechazados por el validador de 'huespedes'")
        return e

    def crear(self, huesped: NuevoHuesped) -> int:
        id_huesped = self._siguiente_id()
        try:
            self._db.huespedes.insert_one({"_id": id_huesped, **self._a_documento(huesped)}, session=self._s)
        except WriteError as e:  # DuplicateKeyError es subclase de WriteError
            raise self._traducir(e) from e
        return id_huesped

    def actualizar(self, id_huesped: int, huesped: NuevoHuesped) -> bool:
        try:
            r = self._db.huespedes.replace_one({"_id": id_huesped}, self._a_documento(huesped), session=self._s)
        except WriteError as e:
            raise self._traducir(e) from e
        return r.matched_count == 1

    def eliminar(self, id_huesped: int) -> bool:
        return self._db.huespedes.delete_one({"_id": id_huesped}, session=self._s).deleted_count == 1

    def contar_reservas_activas(self, id_huesped: int) -> int:
        return self._db.reservas.count_documents(
            {"id_huesped": id_huesped, "estado": {"$in": ESTADOS_ACTIVOS}}, session=self._s)


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


class MongoGestionRepository(_Repo):
    """Consultas de lectura para el panel, la administración y el reporte de ventas (semana 15)."""

    _COLECCIONES = {"huespedes", "habitaciones", "reservas"}

    def listar_reservas(self, estado=None, desde=None, hasta=None, id_huesped=None, limite=500) -> list[ReservaFila]:
        filtro: dict = {}
        if estado:
            filtro["estado"] = estado
        if id_huesped:
            filtro["id_huesped"] = id_huesped
        rango = {}
        if desde:
            rango["$gte"] = a_fecha_bson(desde)
        if hasta:
            rango["$lte"] = a_fecha_bson(hasta)
        if rango:
            filtro["fecha_entrada"] = rango
        tubo = [
            {"$match": filtro},
            {"$sort": {"fecha_entrada": -1, "_id": -1}},
            {"$limit": limite},
            {"$lookup": {"from": "huespedes", "localField": "id_huesped", "foreignField": "_id", "as": "h"}},
            {"$lookup": {"from": "habitaciones", "localField": "id_habitacion", "foreignField": "_id", "as": "hab"}},
            {"$unwind": {"path": "$hab", "preserveNullAndEmptyArrays": True}},
            {"$lookup": {"from": "tipos_habitacion", "localField": "hab.id_tipo", "foreignField": "_id", "as": "t"}},
        ]
        filas = []
        for d in self._db.reservas.aggregate(tubo, session=self._s):
            h = d["h"][0] if d["h"] else {}
            t = d["t"][0] if d["t"] else {}
            filas.append(ReservaFila(
                id_reserva=d["_id"], estado=d["estado"],
                fecha_entrada=d["fecha_entrada"].date(), fecha_salida=d["fecha_salida"].date(),
                numero_personas=d["numero_personas"], tarifa_noche=_dinero(d["tarifa_noche"]), total=_dinero(d["total"]),
                id_huesped=d["id_huesped"], huesped=h.get("nombre", f"Huésped {d['id_huesped']}"),
                habitacion=(d.get("hab") or {}).get("numero", "?"), tipo=t.get("nombre", "?"),
                creada_en=d["creada_en"],
            ))
        return filas

    def cancelar_reserva(self, id_reserva: int) -> bool:
        # Solo CONFIRMADA: al pasar a CANCELADA la reserva sale del índice parcial y sus noches quedan libres.
        r = self._db.reservas.update_one({"_id": id_reserva, "estado": "CONFIRMADA"},
                                         {"$set": {"estado": "CANCELADA"}}, session=self._s)
        return r.modified_count == 1

    def contar(self, coleccion: str, filtro_estado=None) -> int:
        if coleccion not in self._COLECCIONES:
            raise ValueError(coleccion)
        filtro = {"estado": {"$in": filtro_estado}} if filtro_estado else {}
        return self._db[coleccion].count_documents(filtro, session=self._s)

    def ocupadas_en(self, dia: date) -> int:
        return len(self._db.reservas.distinct(
            "id_habitacion", {"estado": {"$in": ESTADOS_ACTIVOS}, "noches": a_fecha_bson(dia)}, session=self._s))

    def listar_tipos(self) -> list[TipoHabitacion]:
        return [TipoHabitacion(d["_id"], d["nombre"], d["capacidad_max"], _dinero(d["tarifa_noche"]))
                for d in self._db.tipos_habitacion.find({}, session=self._s).sort("_id", 1)]

    def actualizar_tipo(self, id_tipo: int, capacidad_max: int, tarifa_noche) -> bool:
        try:
            r = self._db.tipos_habitacion.update_one(
                {"_id": id_tipo},
                {"$set": {"capacidad_max": capacidad_max, "tarifa_noche": a_dinero_bson(tarifa_noche)}},
                session=self._s)
        except WriteError as e:
            if e.code == _VALIDACION_FALLIDA:
                raise DatosInvalidosError("Datos rechazados por el validador de 'tipos_habitacion'") from e
            raise
        return r.matched_count == 1
