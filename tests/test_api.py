"""Pruebas funcionales por API contra MongoDB real (semana 14, actividad 3).

Estado inicial de cada prueba (scripts/reset_db): 24 habitaciones (Estándar 101-112,
Familiar 201-208, Suite 301-304), huéspedes 1-3, reservas: 1) Suite 301 del 20 al 23 de
diciembre CONFIRMADA; 2) Suite 302 mismas fechas CANCELADA; 3) Estándar 101 del 10 al 12
CONFIRMADA. Contador de reservas en 3.

Ejecutar:  pytest -v tests/test_api.py
"""
import threading
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.persistence.db import base, nueva_conexion
from app.persistence.repositories import MongoReservaRepository

api = TestClient(app)

VALIDA = {"id_huesped": 1, "id_tipo": 2, "fecha_entrada": "2026-12-20", "fecha_salida": "2026-12-23", "numero_personas": 3}


def disp(**params):
    q = {"id_tipo": 3, "fecha_entrada": "2026-12-21", "fecha_salida": "2026-12-22", "personas": 2}
    q.update(params)
    return api.get("/api/disponibilidad", params=q)


def reservar(**cambios):
    cuerpo = dict(VALIDA)
    cuerpo.update(cambios)
    return api.post("/api/reservas", json=cuerpo)


def n_reservas() -> int:
    return base().reservas.count_documents({})


def contador() -> int:
    return base().contadores.find_one({"_id": "reserva"})["valor"]


# ================================================================== RF-04 Crear reserva
def test_rf04_valido_201_y_se_recupera_desde_otra_conexion():  # CA-01
    r = reservar()
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["id_reserva"] == 4 and r.headers["location"] == "/api/reservas/4"
    assert cuerpo["habitacion"] == {"id_habitacion": 13, "numero": "201", "tipo": "Familiar"}
    assert (cuerpo["noches"], cuerpo["tarifa_noche"], cuerpo["total"], cuerpo["estado"]) == (3, 200000, 600000, "CONFIRMADA")

    otra = nueva_conexion()  # cliente nuevo, fuera de la API
    try:
        guardada = MongoReservaRepository(otra).buscar_por_id(cuerpo["id_reserva"])
    finally:
        otra.cerrar()
    assert guardada.id_habitacion == 13 and guardada.fecha_entrada == date(2026, 12, 20)
    assert str(guardada.total) == "600000.00"


def test_rf04_rechazo_409_sin_disponibilidad_no_cambia_registros():  # CA-03
    # Las 4 Suites del 21 al 22: la 301 ya está ocupada; se reservan la 302, 303 y 304.
    for numero in ("302", "303", "304"):
        r = reservar(id_tipo=3, fecha_entrada="2026-12-21", fecha_salida="2026-12-22", numero_personas=2)
        assert r.status_code == 201 and r.json()["habitacion"]["numero"] == numero
    antes = n_reservas()
    r = reservar(id_tipo=3, fecha_entrada="2026-12-21", fecha_salida="2026-12-22", numero_personas=2)
    assert r.status_code == 409
    assert r.json() == {"detail": "No hay habitaciones disponibles para esas fechas.", "codigo": "SIN_DISPONIBILIDAD"}
    assert n_reservas() == antes


def test_rf04_capacidad_excedida_422():  # CA-05
    antes = n_reservas()
    r = reservar(id_tipo=1, numero_personas=3)
    assert r.status_code == 422 and r.json()["codigo"] == "CAPACIDAD_EXCEDIDA"
    assert n_reservas() == antes


@pytest.mark.parametrize(
    "entrada,salida",
    [("2026-12-23", "2026-12-20"), ("2026-12-20", "2026-12-20"), ("2026-01-10", "2026-01-12")],
    ids=["salida-antes", "mismo-dia", "en-el-pasado"],
)
def test_rf04_fechas_invalidas_400(entrada, salida):  # CA-06, RN-03, RN-04
    antes = n_reservas()
    r = reservar(fecha_entrada=entrada, fecha_salida=salida)
    assert r.status_code == 400 and r.json()["codigo"] == "FECHAS_INVALIDAS"
    assert n_reservas() == antes


def test_rf04_huesped_inexistente_404_sin_registro_huerfano():  # RN-05
    antes, cont = n_reservas(), contador()
    r = reservar(id_huesped=999)
    assert r.status_code == 404 and r.json() == {"detail": "El huésped no existe.", "codigo": "NO_ENCONTRADO"}
    assert n_reservas() == antes and contador() == cont


def test_rf04_tipo_inexistente_404():  # RN-05
    r = reservar(id_tipo=9)
    assert r.status_code == 404 and r.json()["detail"] == "El tipo de habitación no existe."


@pytest.mark.parametrize(
    "cuerpo,campo",
    [
        ({k: v for k, v in VALIDA.items() if k != "id_huesped"}, "id_huesped"),
        ({**VALIDA, "fecha_entrada": "20/12/2026"}, "fecha_entrada"),
        ({**VALIDA, "numero_personas": 0}, "numero_personas"),
        ({**VALIDA, "huespedId": 1}, "huespedId"),
    ],
    ids=["falta-campo", "fecha-mal-formada", "personas-cero", "campo-desconocido"],
)
def test_rf04_entrada_mal_formada_400(cuerpo, campo):
    antes = n_reservas()
    r = api.post("/api/reservas", json=cuerpo)
    assert r.status_code == 400
    assert r.json()["codigo"] == "DATOS_INVALIDOS" and campo in [e["campo"] for e in r.json()["errores"]]
    assert n_reservas() == antes


def test_rf04_inicio_el_dia_de_salida_de_otra_se_permite():  # CA-04
    r = reservar(id_tipo=3, fecha_entrada="2026-12-23", fecha_salida="2026-12-25", numero_personas=2)
    assert r.status_code == 201 and r.json()["habitacion"]["numero"] == "301"


def test_rf04_consultar_por_id_200_no_modifica():
    creada = reservar().json()
    antes = base().reservas.find_one({"_id": creada["id_reserva"]})
    r = api.get(f"/api/reservas/{creada['id_reserva']}")
    assert r.status_code == 200 and r.json() == creada
    assert base().reservas.find_one({"_id": creada["id_reserva"]}) == antes


def test_rf04_consultar_id_inexistente_404_y_api_sigue_disponible():
    assert base().reservas.count_documents({"_id": 999999}) == 0  # se comprueba que no existe
    r = api.get("/api/reservas/999999")
    assert r.status_code == 404 and r.json() == {"detail": "La reserva no existe.", "codigo": "NO_ENCONTRADO"}
    assert api.get("/api/reservas/1").status_code == 200


@pytest.mark.parametrize("id_invalido", ["abc", "0", "-3", "1.5"])
def test_rf04_consultar_id_invalido_400(id_invalido):
    r = api.get(f"/api/reservas/{id_invalido}")
    assert r.status_code == 400 and r.json()["codigo"] == "DATOS_INVALIDOS"


# ================================================================== RF-02 Consultar disponibilidad
def test_rf02_valido_suites_21_22():  # CA-02
    r = disp()
    assert r.status_code == 200
    cuerpo = r.json()
    assert [h["numero"] for h in cuerpo["habitaciones_disponibles"]] == ["302", "303", "304"]
    assert (cuerpo["tipo"], cuerpo["capacidad"], cuerpo["tarifa_noche"], cuerpo["noches"]) == ("Suite", 3, 280000, 1)


def test_rf02_refleja_reserva_recien_creada():
    reservar(id_tipo=3, fecha_entrada="2026-12-21", fecha_salida="2026-12-22", numero_personas=2)  # toma la 302
    assert [h["numero"] for h in disp().json()["habitaciones_disponibles"]] == ["303", "304"]


def test_rf02_sin_habitaciones_200_lista_vacia():
    for _ in range(3):
        reservar(id_tipo=3, fecha_entrada="2026-12-21", fecha_salida="2026-12-22", numero_personas=2)
    r = disp()
    assert r.status_code == 200 and r.json()["habitaciones_disponibles"] == []


def test_rf02_tipo_inexistente_404():
    assert disp(id_tipo=9).status_code == 404


def test_rf02_capacidad_excedida_422():
    r = disp(personas=4)
    assert r.status_code == 422 and r.json()["codigo"] == "CAPACIDAD_EXCEDIDA"


def test_rf02_fechas_invalidas_400():
    r = disp(fecha_entrada="2026-12-22", fecha_salida="2026-12-21")
    assert r.status_code == 400 and r.json()["codigo"] == "FECHAS_INVALIDAS"


def test_rf02_parametro_faltante_o_mal_formado_400():
    assert api.get("/api/disponibilidad", params={"id_tipo": 3}).status_code == 400
    r = disp(fecha_entrada="mañana")
    assert r.status_code == 400 and r.json()["codigo"] == "DATOS_INVALIDOS"


def test_rf02_consultar_no_modifica_datos():
    antes = n_reservas()
    disp()
    assert n_reservas() == antes


# ================================================================== RNF-03 y RNF-08 a través de la API
def test_rnf03_fallo_despues_de_guardar_responde_500_generico_sin_datos_parciales(monkeypatch):
    original = MongoReservaRepository.guardar

    def guardar_y_fallar(self, reserva):
        original(self, reserva)
        raise RuntimeError("falla simulada: conexión perdida con detalles internos")

    monkeypatch.setattr(MongoReservaRepository, "guardar", guardar_y_fallar)
    antes, cont = n_reservas(), contador()
    r = TestClient(app, raise_server_exceptions=False).post("/api/reservas", json=VALIDA)
    assert r.status_code == 500
    assert r.json() == {"detail": "Ocurrió un error interno. Intente de nuevo más tarde.", "codigo": "ERROR_INTERNO"}
    assert "conexión perdida" not in r.text  # no se exponen detalles técnicos
    assert n_reservas() == antes and contador() == cont


def test_rnf08_diez_solicitudes_simultaneas_por_la_ultima_suite():  # CA-07
    # Del 26 al 28 de diciembre se ocupan la 301, la 302 y la 303: queda UNA sola Suite libre (la 304).
    for _ in range(3):
        assert reservar(id_tipo=3, fecha_entrada="2026-12-26", fecha_salida="2026-12-28", numero_personas=2).status_code == 201
    assert [h["numero"] for h in disp(fecha_entrada="2026-12-26", fecha_salida="2026-12-28").json()["habitaciones_disponibles"]] == ["304"]

    barrera, codigos = threading.Barrier(10), []
    cuerpo = {**VALIDA, "id_tipo": 3, "fecha_entrada": "2026-12-26", "fecha_salida": "2026-12-28", "numero_personas": 2}

    def intentar():
        cliente = TestClient(app)
        barrera.wait()
        codigos.append(cliente.post("/api/reservas", json=cuerpo).status_code)

    hilos = [threading.Thread(target=intentar) for _ in range(10)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(codigos) == [201] + [409] * 9
    suite_304 = base().habitaciones.find_one({"numero": "304"})["_id"]
    activas = base().reservas.count_documents(
        {"id_habitacion": suite_304, "estado": "CONFIRMADA", "noches": datetime(2026, 12, 26)}
    )
    assert activas == 1
