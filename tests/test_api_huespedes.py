"""CRUD de huéspedes por API contra MongoDB real, con permisos por rol (semana 15).

Integración Interfaz(HTTP) -> API -> Servicio -> Repositorio -> MongoDB.
Estado inicial: huéspedes 1 (Ana Torres, ana@example.com), 2 y 3; contador de huéspedes en 3.
Reservas 1 y 3 (huéspedes 1 y 3) están CONFIRMADAS; la 2 (huésped 2) está CANCELADA.

Ejecutar:  pytest -v tests/test_api_huespedes.py
"""
import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.auth.jwt_handler import create_access_token
from app.persistence.db import base

api = TestClient(app)


def token(rol: str, correo: str = "staff@marea.test") -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': correo, 'role': rol})}"}


RECEP, ADMIN = token("recepcionista"), token("admin")
ANA = token("huesped", "ana@example.com")
NUEVO = {"nombre": "María Gómez", "documento": "1033445566", "nacionalidad": "Colombiana",
         "telefono": "3104567890", "correo": "maria@example.com"}


# ------------------------------------------------------------------ permisos
@pytest.mark.parametrize("metodo, ruta", [
    ("get", "/api/huespedes"), ("get", "/api/huespedes/1"), ("post", "/api/huespedes"),
    ("put", "/api/huespedes/1"), ("delete", "/api/huespedes/2"),
])
def test_sin_token_401(metodo, ruta):
    r = api.request(metodo.upper(), ruta, json=NUEVO if metodo in ("post", "put") else None)
    assert r.status_code == 401 and r.json()["codigo"] == "NO_AUTENTICADO"


def test_token_falso_401():
    r = api.get("/api/huespedes", headers={"Authorization": "Bearer no.es.un.token"})
    assert r.status_code == 401


def test_huesped_no_lista_ni_crea_403():
    assert api.get("/api/huespedes", headers=ANA).json()["codigo"] == "SIN_PERMISO"
    r = api.post("/api/huespedes", json=NUEVO, headers=ANA)
    assert r.status_code == 403
    assert base().huespedes.count_documents({}) == 3  # nada se guardó


def test_huesped_ve_solo_su_ficha():
    assert api.get("/api/huespedes/1", headers=ANA).status_code == 200
    assert api.get("/api/huespedes/2", headers=ANA).status_code == 403
    yo = api.get("/api/huespedes/yo", headers=ANA)
    assert yo.status_code == 200 and yo.json()["id_huesped"] == 1


def test_recepcionista_no_elimina_403():
    r = api.delete("/api/huespedes/2", headers=RECEP)
    assert r.status_code == 403
    assert base().huespedes.count_documents({"_id": 2}) == 1


# ------------------------------------------------------------------ CRUD
def test_crear_201_location_y_queda_en_la_base():
    r = api.post("/api/huespedes", json={**NUEVO, "correo": "MARIA@Example.com"}, headers=RECEP)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["id_huesped"] == 4 and r.headers["location"] == "/api/huespedes/4"
    assert cuerpo["correo"] == "maria@example.com"
    assert base().huespedes.find_one({"_id": 4})["documento"] == "1033445566"


def test_listar_y_buscar():
    todos = api.get("/api/huespedes", headers=RECEP).json()
    nombres = [h["nombre"] for h in todos]
    assert len(todos) == 3 and nombres == sorted(nombres)
    filtrados = api.get("/api/huespedes", params={"buscar": "ana@"}, headers=RECEP).json()
    assert [h["id_huesped"] for h in filtrados] == [1]
    # caracteres especiales se buscan literal (no rompen la expresión regular)
    assert api.get("/api/huespedes", params={"buscar": "(*"}, headers=RECEP).json() == []


@pytest.mark.parametrize("cambio, campo", [
    ({"documento": "1020304050"}, "documento"),
    ({"correo": "ANA@EXAMPLE.COM"}, "correo"),
])
def test_crear_duplicado_409_con_campo(cambio, campo):
    r = api.post("/api/huespedes", json={**NUEVO, **cambio}, headers=RECEP)
    assert r.status_code == 409
    assert r.json()["codigo"] == "DATO_DUPLICADO" and r.json()["campo"] == campo
    assert base().huespedes.count_documents({}) == 3


def test_crear_invalido_400_con_errores_por_campo():
    r = api.post("/api/huespedes", json={"nombre": "A", "documento": "x", "correo": "malo"}, headers=RECEP)
    assert r.status_code == 400 and r.json()["codigo"] == "DATOS_INVALIDOS"
    assert {e["campo"] for e in r.json()["errores"]} == {"nombre", "documento", "correo"}


def test_crear_campo_extra_o_faltante_400():
    assert api.post("/api/huespedes", json={**NUEVO, "id_huesped": 9}, headers=RECEP).status_code == 400
    r = api.post("/api/huespedes", json={"nombre": "Solo nombre"}, headers=RECEP)
    assert r.status_code == 400 and r.json()["errores"][0]["campo"] == "documento"


def test_actualizar_200_y_404():
    r = api.put("/api/huespedes/2", json={**NUEVO, "nombre": "Carlos M."}, headers=RECEP)
    assert r.status_code == 200 and r.json()["nombre"] == "Carlos M."
    assert base().huespedes.find_one({"_id": 2})["correo"] == "maria@example.com"
    r = api.put("/api/huespedes/99", json=NUEVO, headers=RECEP)
    assert r.status_code == 404 and r.json()["codigo"] == "NO_ENCONTRADO"


def test_consultar_inexistente_404():
    r = api.get("/api/huespedes/999", headers=RECEP)
    assert r.status_code == 404 and r.json()["codigo"] == "NO_ENCONTRADO"


def test_eliminar_admin_204_y_luego_404():
    assert api.delete("/api/huespedes/2", headers=ADMIN).status_code == 204
    assert base().huespedes.count_documents({"_id": 2}) == 0
    assert api.delete("/api/huespedes/2", headers=ADMIN).status_code == 404


def test_eliminar_con_reserva_activa_409():
    r = api.delete("/api/huespedes/1", headers=ADMIN)
    assert r.status_code == 409 and r.json()["codigo"] == "HUESPED_CON_RESERVAS"
    assert base().huespedes.count_documents({"_id": 1}) == 1


# ------------------------------------------------------------------ reservas con permisos
RESERVA = {"id_huesped": 1, "id_tipo": 2, "fecha_entrada": "2026-12-20", "fecha_salida": "2026-12-23", "numero_personas": 3}


def test_reserva_sin_sesion_401_y_no_guarda():
    antes = base().reservas.count_documents({})
    r = api.post("/api/reservas", json=RESERVA)
    assert r.status_code == 401 and base().reservas.count_documents({}) == antes


def test_huesped_reserva_para_si_201_y_para_otro_403():
    assert api.post("/api/reservas", json=RESERVA, headers=ANA).status_code == 201
    r = api.post("/api/reservas", json={**RESERVA, "id_huesped": 2}, headers=ANA)
    assert r.status_code == 403 and r.json()["codigo"] == "SIN_PERMISO"


def test_huesped_sin_ficha_403():
    r = api.post("/api/reservas", json=RESERVA, headers=token("huesped", "nadie@correo.com"))
    assert r.status_code == 403


def test_huesped_consulta_solo_sus_reservas():
    assert api.get("/api/reservas/1", headers=ANA).status_code == 200    # reserva de Ana
    assert api.get("/api/reservas/3", headers=ANA).status_code == 403    # reserva de Laura
    assert api.get("/api/reservas/3", headers=RECEP).status_code == 200


def test_disponibilidad_sigue_siendo_publica():
    r = api.get("/api/disponibilidad", params={"id_tipo": 1, "fecha_entrada": "2026-12-20",
                                               "fecha_salida": "2026-12-22", "personas": 1})
    assert r.status_code == 200
