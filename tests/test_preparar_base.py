"""Preparación NO destructiva de la base del corte (producción / Atlas), semana 15.

Simula lo que había en Atlas: `marea_test` con fichas de huéspedes creadas al registrarse, pero sin
tipos ni habitaciones. Se usa una base aparte (marea_prep_test) para no tocar la de las pruebas.
"""
import pytest

from app.persistence.db import cliente
from db.datos_prueba import cargar_catalogo_si_falta
from db.esquema import COLECCIONES, asegurar_esquema


@pytest.fixture
def db():
    d = cliente()["marea_prep_test"]
    cliente().drop_database(d.name)
    yield d
    cliente().drop_database(d.name)


def test_agrega_lo_que_falta_sin_borrar_los_huespedes(db):
    db.huespedes.insert_one({"_id": 1, "nombre": "Registrado en producción", "documento": "123456", "correo": "x@y.co",
                             "nacionalidad": None, "telefono": None})
    db.contadores.insert_one({"_id": "huesped", "valor": 1})

    cambios = asegurar_esquema(db) + cargar_catalogo_si_falta(db)

    assert db.huespedes.count_documents({}) == 1                      # no se borró nada
    assert db.contadores.find_one({"_id": "huesped"})["valor"] == 1
    assert db.tipos_habitacion.count_documents({}) == 3 and db.habitaciones.count_documents({}) == 24
    assert db.reservas.count_documents({}) == 0                       # sin datos de prueba
    assert set(COLECCIONES) <= set(db.list_collection_names())
    assert "ux_reserva_sin_solape" in db.reservas.index_information()
    assert "ux_huesped_documento" in db.huespedes.index_information()
    assert any("habitaciones cargadas" in c for c in cambios)


def test_es_idempotente(db):
    asegurar_esquema(db), cargar_catalogo_si_falta(db)
    db.tipos_habitacion.update_one({"_id": 2}, {"$set": {"capacidad_max": 5}})  # p. ej. el admin cambió algo
    assert asegurar_esquema(db) == [] and cargar_catalogo_si_falta(db) == []
    assert db.tipos_habitacion.find_one({"_id": 2})["capacidad_max"] == 5      # se respeta
    assert db.habitaciones.count_documents({}) == 24
