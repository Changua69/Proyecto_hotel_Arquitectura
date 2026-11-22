"""Correos que no se repiten.

1. Huéspedes del corte (`marea_test.huespedes`): índice único sobre `correo`, sin distinguir
   mayúsculas; varios huéspedes pueden no tener correo.
2. Registro de usuarios (`POST /register`, ruta heredada del login): 409 si el correo ya existe,
   sin distinguir mayúsculas ni espacios, también con registros simultáneos.
   Estas pruebas se omiten si no están instaladas las dependencias del login (instaladores.txt).
"""
import threading

import pytest
from pymongo.errors import DuplicateKeyError

from app.persistence.db import base


# ------------------------------------------------------------------ huéspedes del corte
def nuevo_huesped(_id: int, documento: str, correo):
    return {"_id": _id, "nombre": "Prueba", "documento": documento, "nacionalidad": None,
            "telefono": None, "correo": correo}


def test_huesped_con_correo_repetido_se_rechaza_sin_importar_mayusculas():
    # ana@example.com ya existe en los datos de prueba (huésped 1)
    with pytest.raises(DuplicateKeyError):
        base().huespedes.insert_one(nuevo_huesped(10, "555", "ANA@Example.com"))
    assert base().huespedes.count_documents({}) == 3


def test_varios_huespedes_sin_correo_si_se_permiten():
    base().huespedes.insert_one(nuevo_huesped(10, "555", None))
    base().huespedes.insert_one(nuevo_huesped(11, "556", None))
    assert base().huespedes.count_documents({"correo": None}) == 2


# ------------------------------------------------------------------ registro de usuarios (login heredado)
@pytest.fixture
def registro(monkeypatch):
    for modulo in ("jose", "passlib", "email_validator", "multipart"):
        pytest.importorskip(modulo)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routes import auth

    usuarios = base()["usuarios_prueba"]  # nunca toca hotel_db
    usuarios.drop()
    monkeypatch.setattr(auth, "users_collection", usuarios)
    auth.asegurar_email_unico()
    from app.api.errores import registrar_manejadores

    app = FastAPI()
    app.include_router(auth.router)
    registrar_manejadores(app)  # errores del corte (p. ej. documento repetido al crear la ficha)
    yield TestClient(app), usuarios
    usuarios.drop()


def datos(email: str) -> dict:
    return {"name": "Ana", "email": email, "password": "clave1234", "phone": "3001234567", "documento": "55667788"}


def test_registro_con_correo_repetido_409(registro):
    api, usuarios = registro
    assert api.post("/register", json=datos("ana@correo.com")).status_code == 201
    r = api.post("/register", json=datos("  ANA@Correo.com "))
    assert r.status_code == 409 and r.json()["detail"] == "Ya existe una cuenta con ese correo."
    assert usuarios.count_documents({}) == 1


def test_login_no_distingue_mayusculas(registro):
    api, _ = registro
    api.post("/register", json=datos("ana@correo.com"))
    r = api.post("/login", data={"username": "ANA@CORREO.COM", "password": "clave1234"})
    assert r.status_code == 200 and r.json()["role"] == "huesped"


def test_registros_simultaneos_con_el_mismo_correo_solo_uno(registro):
    api, usuarios = registro
    barrera, codigos = threading.Barrier(5), []

    def intentar():
        barrera.wait()
        codigos.append(api.post("/register", json=datos("laura@correo.com")).status_code)

    hilos = [threading.Thread(target=intentar) for _ in range(5)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(codigos) == [201] + [409] * 4
    assert usuarios.count_documents({}) == 1
