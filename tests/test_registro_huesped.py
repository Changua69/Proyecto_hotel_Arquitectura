"""Registro del huésped = cuenta + ficha de huésped (semana 15).

Quien se registra en "Registrarse" queda como huésped del hotel con el mismo correo, sin pasar por
recepción, y por eso ve sus reservas en "Mis reservas". Las cuentas se guardan en
marea_test.usuarios_prueba (nunca en hotel_db); las fichas, en la base del corte.
"""
import pytest
from fastapi.testclient import TestClient

from app.api.app import crear_app
from app.auth.jwt_handler import create_access_token
from app.persistence.db import base
from app.routes import auth


@pytest.fixture
def api(monkeypatch):
    usuarios = base()["usuarios_prueba"]
    usuarios.drop()
    monkeypatch.setattr(auth, "users_collection", usuarios)
    auth.asegurar_email_unico()
    app = crear_app()
    app.include_router(auth.router)
    yield TestClient(app), usuarios
    usuarios.drop()


def registro(email="pedro@correo.com", documento="99887766", **extra):
    return {"name": "Pedro Pérez", "email": email, "password": "Clave12345", "phone": "300-123-4567",
            "documento": documento, **extra}


def sesion(api, email, clave="Clave12345"):
    t = api.post("/login", data={"username": email, "password": clave}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def test_registrarse_crea_cuenta_y_ficha_unidas_por_el_correo(api):
    c, usuarios = api
    assert c.post("/register", json=registro(email="Pedro@Correo.com")).status_code == 201
    ficha = base().huespedes.find_one({"correo": "pedro@correo.com"})
    assert ficha["nombre"] == "Pedro Pérez" and ficha["documento"] == "99887766" and ficha["telefono"] == "3001234567"
    yo = c.get("/api/huespedes/yo", headers=sesion(c, "pedro@correo.com"))
    assert yo.status_code == 200 and yo.json()["id_huesped"] == ficha["_id"] == 4


def test_huesped_registrado_ve_la_reserva_que_le_hacen(api):
    c, _ = api
    c.post("/register", json=registro())
    pedro = sesion(c, "pedro@correo.com")
    recep = {"Authorization": f"Bearer {create_access_token({'sub': 'r@marea.test', 'role': 'recepcionista'})}"}
    r = c.post("/api/reservas", headers=recep, json={"id_huesped": 4, "id_tipo": 1, "fecha_entrada": "2026-12-26",
                                                     "fecha_salida": "2026-12-28", "numero_personas": 1})
    assert r.status_code == 201
    assert [f["id_reserva"] for f in c.get("/api/reservas", headers=pedro).json()] == [r.json()["id_reserva"]]


def test_sin_documento_no_se_crea_nada(api):
    c, usuarios = api
    r = c.post("/register", json=registro(documento=None))
    assert r.status_code == 400 and r.json()["errores"][0]["campo"] == "documento"
    assert usuarios.count_documents({}) == 0 and base().huespedes.count_documents({}) == 3


def test_documento_de_otro_huesped_409_y_no_crea_la_cuenta(api):
    c, usuarios = api
    r = c.post("/register", json=registro(documento="1020304050"))  # documento de Ana
    assert r.status_code == 409 and r.json()["campo"] == "documento"
    assert usuarios.count_documents({}) == 0


def test_si_recepcion_ya_lo_registro_se_une_a_esa_ficha(api):
    c, _ = api
    assert c.post("/register", json=registro(email="ana@example.com", documento=None)).status_code == 201
    assert base().huespedes.count_documents({}) == 3  # no se duplicó
    assert c.get("/api/huespedes/yo", headers=sesion(c, "ana@example.com")).json()["id_huesped"] == 1


def test_clave_corta_400(api):
    c, usuarios = api
    assert c.post("/register", json={**registro(), "password": "123"}).status_code == 400
    assert usuarios.count_documents({}) == 0 and base().huespedes.count_documents({}) == 3


def test_cuenta_antigua_completa_su_ficha_una_vez(api):
    c, _ = api
    viejo = {"Authorization": f"Bearer {create_access_token({'sub': 'corotos@gmail.com', 'role': 'huesped'})}"}
    assert c.get("/api/huespedes/yo", headers=viejo).status_code == 404
    r = c.post("/api/huespedes/yo", headers=viejo, json={"nombre": "Corotos", "documento": "11223344"})
    assert r.status_code == 201 and r.json()["correo"] == "corotos@gmail.com"
    assert c.get("/api/huespedes/yo", headers=viejo).status_code == 200
    again = c.post("/api/huespedes/yo", headers=viejo, json={"nombre": "Otro", "documento": "55555555"})
    assert again.status_code == 409
    # el correo no se puede cambiar desde el cuerpo
    assert c.post("/api/huespedes/yo", headers=viejo, json={"nombre": "X", "documento": "1", "correo": "a@b.co"}).status_code == 400


def test_personal_no_usa_mi_ficha(api):
    c, _ = api
    recep = {"Authorization": f"Bearer {create_access_token({'sub': 'r@marea.test', 'role': 'recepcionista'})}"}
    assert c.post("/api/huespedes/yo", headers=recep, json={"nombre": "Rec", "documento": "12345678"}).status_code == 403
