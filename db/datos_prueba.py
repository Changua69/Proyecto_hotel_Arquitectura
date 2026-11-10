"""Datos de prueba con estado inicial conocido (semana 13).

Fechas de referencia: diciembre de 2026 (futuras, cumplen RN-04).
Mantener estos datos como referencia en las semanas 2 y 3.
"""
from datetime import date, datetime

from pymongo.database import Database

from app.persistence.repositories import a_dinero_bson, a_fecha_bson, noches_de

# Tipos (tarifas de ejemplo; deben confirmarse con el Resort)
TIPOS = [
    {"_id": 1, "nombre": "Estándar", "capacidad_max": 2, "tarifa_noche": 120000},
    {"_id": 2, "nombre": "Familiar", "capacidad_max": 4, "tarifa_noche": 200000},
    {"_id": 3, "nombre": "Suite", "capacidad_max": 3, "tarifa_noche": 280000},
]

# 24 habitaciones: Estándar 101-112, Familiar 201-208, Suite 301-304 (ids 1..24 en ese orden)
HABITACIONES = (
    [str(100 + n) for n in range(1, 13)] + [str(200 + n) for n in range(1, 9)] + [str(300 + n) for n in range(1, 5)]
)

HUESPEDES = [
    {"_id": 1, "nombre": "Ana Torres", "documento": "1020304050", "nacionalidad": "Colombiana",
     "telefono": "3001234567", "correo": "ana@example.com"},
    {"_id": 2, "nombre": "Carlos Méndez", "documento": "79888777", "nacionalidad": "Colombiana",
     "telefono": "3109876543", "correo": "carlos@example.com"},
    {"_id": 3, "nombre": "Laura Smith", "documento": "P12345678", "nacionalidad": "Estadounidense",
     "telefono": "3205551234", "correo": "laura@example.com"},
]

# Reservas preexistentes para probar solapes
#  R1: Suite 301 ocupada del 20 al 23 de diciembre (CONFIRMADA)  -> CA-02, CA-04
#  R2: Suite 302 mismas fechas pero CANCELADA (no bloquea)        -> reserva inactiva
#  R3: Estándar 101 del 10 al 12 de diciembre (CONFIRMADA)
RESERVAS = [
    (1, 1, "301", date(2026, 12, 20), date(2026, 12, 23), 2, 280000, 840000, "CONFIRMADA"),
    (2, 2, "302", date(2026, 12, 20), date(2026, 12, 23), 2, 280000, 840000, "CANCELADA"),
    (3, 3, "101", date(2026, 12, 10), date(2026, 12, 12), 1, 120000, 240000, "CONFIRMADA"),
]


def cargar_datos(db: Database) -> None:
    db.tipos_habitacion.insert_many(
        [{**t, "tarifa_noche": a_dinero_bson(t["tarifa_noche"])} for t in TIPOS]
    )

    id_por_numero = {}
    docs = []
    for i, numero in enumerate(HABITACIONES, start=1):
        id_tipo = int(numero[0])  # 1xx Estándar, 2xx Familiar, 3xx Suite
        docs.append({"_id": i, "numero": numero, "id_tipo": id_tipo, "estado": "LIBRE"})
        id_por_numero[numero] = i
    db.habitaciones.insert_many(docs)

    db.huespedes.insert_many(HUESPEDES)

    creada = datetime(2026, 11, 1, 9, 0, 0)
    db.reservas.insert_many([
        {
            "_id": rid, "id_huesped": hues, "id_habitacion": id_por_numero[num],
            "fecha_entrada": a_fecha_bson(ent), "fecha_salida": a_fecha_bson(sal), "noches": noches_de(ent, sal),
            "numero_personas": pers, "tarifa_noche": a_dinero_bson(tarifa), "total": a_dinero_bson(total),
            "estado": estado, "creada_en": creada,
        }
        for rid, hues, num, ent, sal, pers, tarifa, total, estado in RESERVAS
    ])

    # El contador continúa después de los ids explícitos (equivale a setval de una secuencia).
    db.contadores.insert_one({"_id": "reserva", "valor": max(r[0] for r in RESERVAS)})


def verificacion(db: Database) -> dict:
    """Conteos esperados: Estándar 12, Familiar 8, Suite 4; 3 huéspedes; 2 CONFIRMADA y 1 CANCELADA."""
    por_tipo = {
        d["_id"]: d["habitaciones"]
        for d in db.habitaciones.aggregate([
            {"$lookup": {"from": "tipos_habitacion", "localField": "id_tipo", "foreignField": "_id", "as": "t"}},
            {"$group": {"_id": {"$first": "$t.nombre"}, "habitaciones": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ])
    }
    por_estado = {
        d["_id"]: d["n"]
        for d in db.reservas.aggregate([{"$group": {"_id": "$estado", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}])
    }
    return {
        "habitaciones_por_tipo": por_tipo,
        "huespedes": db.huespedes.count_documents({}),
        "reservas_por_estado": por_estado,
    }
