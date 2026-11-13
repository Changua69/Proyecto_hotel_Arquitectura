"""Esquema mínimo del corte vertical en MongoDB (RF-02 disponibilidad y RF-04 reserva).

MongoDB no exige esquema, así que las reglas de integridad se declaran aquí:
- Validadores $jsonSchema por colección (equivalen a NOT NULL, tipos y CHECK).
- $expr en `reservas`: fecha_salida > fecha_entrada (RN-03).
- Índices únicos (equivalen a UNIQUE).
- Índice único PARCIAL y multiclave sobre (id_habitacion, noches) solo para reservas activas:
  dos reservas CONFIRMADA/EN_CURSO de la misma habitación no pueden compartir una noche (RN-01).
  Es el equivalente de la restricción de exclusión y funciona también con solicitudes simultáneas.
  Requiere MongoDB >= 6.0 ($in en partialFilterExpression).

Es idempotente: `crear_esquema` borra y recrea las colecciones del corte.
"""
from pymongo import ASCENDING
from pymongo.database import Database

COLECCIONES = ("tipos_habitacion", "habitaciones", "huespedes", "reservas", "contadores")
ESTADOS_HABITACION = ["LIBRE", "RESERVADA", "OCUPADA", "EN_LIMPIEZA"]
ESTADOS_RESERVA = ["CONFIRMADA", "EN_CURSO", "FINALIZADA", "CANCELADA"]

_POSITIVO_DECIMAL = {"bsonType": "decimal", "minimum": 0, "exclusiveMinimum": True}  # > 0

VALIDADORES = {
    # Catálogo de tipos: aporta capacidad (RN-02) y tarifa (cálculo del total).
    "tipos_habitacion": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "nombre", "capacidad_max", "tarifa_noche"],
            "properties": {
                "_id": {"bsonType": "int"},
                "nombre": {"bsonType": "string", "maxLength": 30},
                "capacidad_max": {"bsonType": "int", "minimum": 1},
                "tarifa_noche": _POSITIVO_DECIMAL,
            },
        }
    },
    # Habitaciones físicas del resort (24).
    "habitaciones": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "numero", "id_tipo", "estado"],
            "properties": {
                "_id": {"bsonType": "int"},
                "numero": {"bsonType": "string", "maxLength": 10},
                "id_tipo": {"bsonType": "int"},
                "estado": {"enum": ESTADOS_HABITACION},
            },
        }
    },
    # Huéspedes. En el corte solo se consultan por id (RF-04).
    "huespedes": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "nombre", "documento"],
            "properties": {
                "_id": {"bsonType": "int"},
                "nombre": {"bsonType": "string", "maxLength": 100},
                "documento": {"bsonType": "string", "maxLength": 30},
                "nacionalidad": {"bsonType": ["string", "null"]},
                "telefono": {"bsonType": ["string", "null"]},
                "correo": {"bsonType": ["string", "null"]},
            },
        }
    },
    # Reservas. `noches` = cada noche ocupada del rango [entrada, salida).
    "reservas": {
        "$and": [
            {
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": [
                        "_id", "id_huesped", "id_habitacion", "fecha_entrada", "fecha_salida", "noches",
                        "numero_personas", "tarifa_noche", "total", "estado", "creada_en",
                    ],
                    "properties": {
                        "_id": {"bsonType": "int"},
                        "id_huesped": {"bsonType": "int"},
                        "id_habitacion": {"bsonType": "int"},
                        "fecha_entrada": {"bsonType": "date"},
                        "fecha_salida": {"bsonType": "date"},
                        "noches": {"bsonType": "array", "minItems": 1, "items": {"bsonType": "date"}},
                        "numero_personas": {"bsonType": "int", "minimum": 1},
                        "tarifa_noche": _POSITIVO_DECIMAL,
                        "total": _POSITIVO_DECIMAL,
                        "estado": {"enum": ESTADOS_RESERVA},
                        "creada_en": {"bsonType": "date"},
                    },
                }
            },
            {"$expr": {"$gt": ["$fecha_salida", "$fecha_entrada"]}},  # RN-03
        ]
    },
}


def crear_esquema(db: Database) -> None:
    for nombre in COLECCIONES:
        db.drop_collection(nombre)
    for nombre, validador in VALIDADORES.items():
        db.create_collection(nombre, validator=validador, validationLevel="strict", validationAction="error")
    db.create_collection("contadores")

    db.tipos_habitacion.create_index("nombre", unique=True, name="ux_tipo_nombre")
    db.habitaciones.create_index("numero", unique=True, name="ux_habitacion_numero")
    db.habitaciones.create_index("id_tipo", name="ix_habitacion_tipo")
    db.huespedes.create_index("documento", unique=True, name="ux_huesped_documento")
    db.reservas.create_index(
        [("id_habitacion", ASCENDING), ("fecha_entrada", ASCENDING), ("fecha_salida", ASCENDING)],
        name="ix_reserva_habitacion_fechas",
    )
    db.reservas.create_index(
        [("id_habitacion", ASCENDING), ("noches", ASCENDING)],
        unique=True,
        partialFilterExpression={"estado": {"$in": ["CONFIRMADA", "EN_CURSO"]}},
        name="ux_reserva_sin_solape",
    )
