"""Modificar una reserva y check-in / check-out (semana 15), contra MongoDB real.

Estado inicial: reserva 1 = Ana (huésped 1), Suite 301, 20-23 dic 2026, CONFIRMADA, $280.000/noche.
Reserva 3 = Laura (huésped 3), Estándar 101, 10-12 dic 2026, CONFIRMADA. Suites 302-304 libres.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.auth.jwt_handler import create_access_token
from app.persistence.db import base
from app.persistence.proveedor import MongoProveedor
from app.services.errores import EstadoReservaError
from app.services.gestion import GestionReservasService

api = TestClient(app)


def token(rol, correo="staff@marea.test"):
    return {"Authorization": f"Bearer {create_access_token({'sub': correo, 'role': rol})}"}


RECEP, ANA = token("recepcionista"), token("huesped", "ana@example.com")


def cambio(entrada, salida, personas=2):
    return {"fecha_entrada": entrada, "fecha_salida": salida, "numero_personas": personas}


def crear(entrada, salida, tipo=3, huesped=2):
    r = api.post("/api/reservas", headers=RECEP, json={"id_huesped": huesped, "id_tipo": tipo,
                 "fecha_entrada": entrada, "fecha_salida": salida, "numero_personas": 1})
    assert r.status_code == 201
    return r.json()


# ------------------------------------------------------------------ modificar
def test_huesped_alarga_su_reserva_conserva_habitacion_y_tarifa():
    r = api.put("/api/reservas/1", headers=ANA, json=cambio("2026-12-20", "2026-12-25", 3))
    assert r.status_code == 200
    c = r.json()
    assert c["habitacion"]["numero"] == "301" and c["noches"] == 5 and c["total"] == 280000 * 5
    d = base().reservas.find_one({"_id": 1})
    assert len(d["noches"]) == 5 and d["numero_personas"] == 3


def test_si_su_habitacion_se_ocupa_se_cambia_a_otra_del_mismo_tipo():
    crear("2026-12-23", "2026-12-26")  # toma la 301 (libre desde el 23, día de salida de Ana)
    crear("2026-12-23", "2026-12-26")  # toma la 302
    r = api.put("/api/reservas/1", headers=RECEP, json=cambio("2026-12-21", "2026-12-25"))
    assert r.status_code == 200 and r.json()["habitacion"]["numero"] == "303"


def test_sin_disponibilidad_409_y_queda_como_estaba():
    for _ in range(4):
        crear("2026-12-24", "2026-12-26")  # 301, 302, 303 y 304 quedan ocupadas desde el 24
    antes = base().reservas.find_one({"_id": 1})
    r = api.put("/api/reservas/1", headers=RECEP, json=cambio("2026-12-20", "2026-12-26"))
    assert r.status_code == 409 and r.json()["codigo"] == "SIN_DISPONIBILIDAD"
    assert base().reservas.find_one({"_id": 1}) == antes


@pytest.mark.parametrize("datos, http, codigo", [
    (cambio("2026-12-23", "2026-12-20"), 400, "FECHAS_INVALIDAS"),
    (cambio("2020-01-01", "2020-01-03"), 400, "FECHAS_INVALIDAS"),
    (cambio("2026-12-20", "2026-12-23", 9), 422, "CAPACIDAD_EXCEDIDA"),
])
def test_validaciones(datos, http, codigo):
    r = api.put("/api/reservas/1", headers=RECEP, json=datos)
    assert r.status_code == http and r.json()["codigo"] == codigo


def test_permisos_y_estados():
    assert api.put("/api/reservas/3", headers=ANA, json=cambio("2026-12-10", "2026-12-13")).status_code == 403
    assert api.put("/api/reservas/999", headers=RECEP, json=cambio("2026-12-10", "2026-12-13")).status_code == 404
    r = api.put("/api/reservas/2", headers=RECEP, json=cambio("2026-12-10", "2026-12-13"))  # cancelada
    assert r.status_code == 409 and r.json()["codigo"] == "RESERVA_NO_MODIFICABLE"
    assert api.put("/api/reservas/1", json=cambio("2026-12-20", "2026-12-24")).status_code == 401


# ------------------------------------------------------------------ check-in / check-out
def servicio(dia):
    return GestionReservasService(MongoProveedor(), hoy=lambda: dia)


def test_check_in_y_check_out_completos():
    with pytest.raises(EstadoReservaError):
        servicio(date(2026, 12, 19)).check_in(1)          # antes de la llegada
    servicio(date(2026, 12, 20)).check_in(1)
    assert base().reservas.find_one({"_id": 1})["estado"] == "EN_CURSO"
    assert base().habitaciones.find_one({"_id": 21})["estado"] == "OCUPADA"  # 301
    with pytest.raises(EstadoReservaError):
        servicio(date(2026, 12, 20)).check_in(1)          # ya está en curso
    servicio(date(2026, 12, 22)).check_out(1)
    assert base().reservas.find_one({"_id": 1})["estado"] == "FINALIZADA"
    assert base().habitaciones.find_one({"_id": 21})["estado"] == "LIBRE"
    # salió antes: la noche del 22 queda libre para otra reserva de Suite
    assert crear("2026-12-22", "2026-12-23")["habitacion"]["numero"] == "301"


def test_check_out_solo_en_curso_y_api_solo_personal():
    with pytest.raises(EstadoReservaError):
        servicio(date(2026, 12, 20)).check_out(1)
    assert api.post("/api/reservas/1/checkin", headers=ANA).status_code == 403
    r = api.post("/api/reservas/1/checkin", headers=RECEP)  # hoy es antes del 20 dic 2026
    assert r.status_code == 409 and r.json()["codigo"] == "ESTADO_NO_PERMITE"
    assert api.post("/api/reservas/999/checkout", headers=RECEP).status_code == 404
