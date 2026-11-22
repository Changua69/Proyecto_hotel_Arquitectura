"""Panel, gestión de reservas, administración y reporte de ventas por API (semana 15).

Contra MongoDB real (base de prueba). Las cuentas se guardan en `marea_test.usuarios_prueba`
(nunca en hotel_db). Estado inicial: reservas 1 (Suite 301, 20-23 dic, CONFIRMADA, $840.000),
2 (Suite 302, CANCELADA) y 3 (Estándar 101, 10-12 dic, CONFIRMADA, $240.000).
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api import gestion
from app.api.app import app
from app.auth.jwt_handler import create_access_token
from app.persistence.db import base
from app.persistence.usuarios import MongoUsuarioRepository


def token(rol: str, correo: str = "staff@marea.test") -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': correo, 'role': rol})}"}


RECEP, ADMIN, ANA = token("recepcionista"), token("admin", "admin@marea.test"), token("huesped", "ana@example.com")
DIC = {"desde": "2026-12-01", "hasta": "2026-12-31"}


@pytest.fixture
def api():
    usuarios = base()["usuarios_prueba"]
    usuarios.drop()
    usuarios.create_index("email", unique=True)
    usuarios.insert_one({"email": "admin@marea.test", "name": "Admin", "role": "admin", "password": "x"})
    app.dependency_overrides[gestion.repo_usuarios] = lambda: MongoUsuarioRepository(usuarios)
    yield TestClient(app)
    app.dependency_overrides.pop(gestion.repo_usuarios, None)
    usuarios.drop()


# ------------------------------------------------------------------ panel y reservas
def test_resumen_del_panel(api):
    r = api.get("/api/panel/resumen", headers=RECEP)
    assert r.status_code == 200
    c = r.json()
    assert (c["huespedes"], c["habitaciones"], c["reservas_activas"]) == (3, 24, 2)
    assert api.get("/api/panel/resumen", headers=ANA).status_code == 403
    assert api.get("/api/panel/resumen").status_code == 401


def test_listar_reservas_filtros_y_huesped_solo_las_suyas(api):
    todas = api.get("/api/reservas", headers=RECEP).json()
    assert {f["id_reserva"] for f in todas} == {1, 2, 3}
    assert todas[0]["huesped"] and todas[0]["habitacion"] and todas[0]["tipo"]
    canceladas = api.get("/api/reservas", params={"estado": "CANCELADA"}, headers=RECEP).json()
    assert [f["id_reserva"] for f in canceladas] == [2]
    assert [f["id_reserva"] for f in api.get("/api/reservas", headers=ANA).json()] == [1]
    r = api.get("/api/reservas", params={"estado": "RARO"}, headers=RECEP)
    assert r.status_code == 400 and r.json()["codigo"] == "DATOS_INVALIDOS"
    r = api.get("/api/reservas", params={"desde": "2026-12-31", "hasta": "2026-12-01"}, headers=RECEP)
    assert r.status_code == 400 and r.json()["codigo"] == "FECHAS_INVALIDAS"


def test_cancelar_libera_la_habitacion(api):
    q = {"id_tipo": 3, "fecha_entrada": "2026-12-20", "fecha_salida": "2026-12-23", "personas": 1}
    antes = [h["numero"] for h in api.get("/api/disponibilidad", params=q).json()["habitaciones_disponibles"]]
    assert "301" not in antes
    assert api.post("/api/reservas/1/cancelar", headers=RECEP).status_code == 204
    assert base().reservas.find_one({"_id": 1})["estado"] == "CANCELADA"
    despues = [h["numero"] for h in api.get("/api/disponibilidad", params=q).json()["habitaciones_disponibles"]]
    assert "301" in despues
    r = api.post("/api/reservas/1/cancelar", headers=RECEP)  # ya cancelada
    assert r.status_code == 409 and r.json()["codigo"] == "RESERVA_NO_CANCELABLE"
    assert api.post("/api/reservas/999/cancelar", headers=RECEP).status_code == 404
    assert api.post("/api/reservas/3/cancelar", headers=ANA).status_code == 403


# ------------------------------------------------------------------ reporte de ventas
def test_reporte_json_excluye_canceladas(api):
    r = api.get("/api/reportes/ventas", params=DIC, headers=ADMIN)
    assert r.status_code == 200
    c = r.json()
    assert c["total"] == 840000 + 240000 and c["reservas_vendidas"] == 2 and c["canceladas"] == 1
    assert c["noches"] == 5
    assert {l["grupo"]: l["total"] for l in c["por_tipo"]} == {"Suite": 840000, "Estándar": 240000}


def test_reporte_pdf_se_descarga(api):
    r = api.get("/api/reportes/ventas.pdf", params=DIC, headers=ADMIN)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and len(r.content) > 1500
    assert 'filename="reporte_ventas_2026-12-01_2026-12-31.pdf"' in r.headers["content-disposition"]


def test_reporte_vacio_tambien_genera_pdf(api):
    r = api.get("/api/reportes/ventas.pdf", params={"desde": "2030-01-01", "hasta": "2030-01-31"}, headers=ADMIN)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


@pytest.mark.parametrize("params, http", [
    ({"desde": "2026-12-31", "hasta": "2026-12-01"}, 400),
    ({"desde": "2026-13-01", "hasta": "2026-12-31"}, 400),
    ({"desde": "2026-12-01"}, 400),
    ({"desde": "2025-01-01", "hasta": "2026-12-31"}, 400),
])
def test_reporte_rangos_invalidos(api, params, http):
    assert api.get("/api/reportes/ventas.pdf", params=params, headers=ADMIN).status_code == http


def test_reporte_solo_admin(api):
    assert api.get("/api/reportes/ventas.pdf", params=DIC, headers=RECEP).status_code == 403


# ------------------------------------------------------------------ administración
def test_crear_usuario_y_duplicado(api):
    nuevo = {"email": "Recep2@Marea.test", "nombre": "Recepción 2", "rol": "recepcionista", "clave": "ClaveSegura1"}
    r = api.post("/api/admin/usuarios", json=nuevo, headers=ADMIN)
    assert r.status_code == 201 and r.json() == {"email": "recep2@marea.test", "nombre": "Recepción 2", "rol": "recepcionista"}
    guardado = base()["usuarios_prueba"].find_one({"email": "recep2@marea.test"})
    assert guardado["password"].startswith("$2")  # se guarda el hash, no la clave
    assert "password" not in str(api.get("/api/admin/usuarios", headers=ADMIN).json())
    r = api.post("/api/admin/usuarios", json=nuevo, headers=ADMIN)
    assert r.status_code == 409 and r.json()["campo"] == "email"


def test_crear_usuario_invalido_400(api):
    r = api.post("/api/admin/usuarios", json={"email": "x", "nombre": "A", "rol": "jefe", "clave": "123"}, headers=ADMIN)
    assert r.status_code == 400
    assert {e["campo"] for e in r.json()["errores"]} == {"email", "nombre", "rol", "clave"}


def test_reglas_de_roles(api):
    api.post("/api/admin/usuarios", json={"email": "r@marea.test", "nombre": "Rec", "rol": "recepcionista", "clave": "ClaveSegura1"}, headers=ADMIN)
    r = api.put("/api/admin/usuarios/r@marea.test/rol", json={"rol": "admin"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["rol"] == "admin"
    # no puede quitarse su propio rol ni borrarse
    assert api.put("/api/admin/usuarios/admin@marea.test/rol", json={"rol": "huesped"}, headers=ADMIN).status_code == 409
    assert api.delete("/api/admin/usuarios/admin@marea.test", headers=ADMIN).json()["codigo"] == "OPERACION_NO_PERMITIDA"
    assert api.delete("/api/admin/usuarios/r@marea.test", headers=ADMIN).status_code == 204
    assert api.delete("/api/admin/usuarios/r@marea.test", headers=ADMIN).status_code == 404
    assert api.get("/api/admin/usuarios", headers=RECEP).status_code == 403


def test_ultimo_admin_no_se_degrada(api):
    otro_admin = token("admin", "otro@marea.test")  # token válido de un admin que ya no está en la base
    r = api.put("/api/admin/usuarios/admin@marea.test/rol", json={"rol": "huesped"}, headers=otro_admin)
    assert r.status_code == 409 and "al menos un administrador" in r.json()["detail"]


def test_actualizar_tarifa(api):
    r = api.put("/api/admin/tipos/2", json={"capacidad_max": 5, "tarifa_noche": 210000}, headers=ADMIN)
    assert r.status_code == 200 and r.json() == {"id_tipo": 2, "nombre": "Familiar", "capacidad_max": 5, "tarifa_noche": 210000}
    q = {"id_tipo": 2, "fecha_entrada": "2026-12-20", "fecha_salida": "2026-12-21", "personas": 5}
    assert api.get("/api/disponibilidad", params=q).json()["tarifa_noche"] == 210000
    assert api.put("/api/admin/tipos/9", json={"capacidad_max": 2, "tarifa_noche": 1}, headers=ADMIN).status_code == 404
    r = api.put("/api/admin/tipos/2", json={"capacidad_max": 0, "tarifa_noche": -1}, headers=ADMIN)
    assert r.status_code == 400 and len(r.json()["errores"]) == 2
    assert api.put("/api/admin/tipos/2", json={"capacidad_max": 4, "tarifa_noche": 1}, headers=RECEP).status_code == 403
    assert len(api.get("/api/admin/tipos", headers=RECEP).json()) == 3


# ------------------------------------------------------------------ portal del huésped: Mis reservas
def test_mis_reservas_solo_las_propias_con_todos_sus_datos(api):
    filas = api.get("/api/reservas", headers=ANA).json()
    assert [f["id_reserva"] for f in filas] == [1]
    assert filas[0]["habitacion"] == "301" and filas[0]["tipo"] == "Suite" and filas[0]["total"] == 840000
    # aunque pida un estado, sigue viendo solo lo suyo
    assert api.get("/api/reservas", params={"estado": "CANCELADA"}, headers=ANA).json() == []


def test_mis_reservas_cuenta_sin_ficha(api):
    sin_ficha = token("huesped", "nadie@correo.com")
    assert api.get("/api/huespedes/yo", headers=sin_ficha).status_code == 404
    assert api.get("/api/reservas", headers=sin_ficha).json() == []
