"""Errores que no son de negocio, sin base real (semana 14).

- Si la base no está disponible: 503 controlado, la API no se cae.
- Si ocurre un fallo inesperado: 500 con mensaje genérico; el detalle solo queda en el log.
Se reemplaza el proveedor de repositorios de la API por uno que falla a propósito.
"""
import pytest
from fastapi.testclient import TestClient

from app.api import rutas
from app.api.app import crear_app
from app.auth.jwt_handler import create_access_token
from app.persistence.errors import BaseNoDisponibleError

pytestmark = pytest.mark.sin_base


class ProveedorQueFalla:
    def __init__(self, error: Exception):
        self.error = error

    def leer(self, fn):
        raise self.error

    def escribir(self, fn):
        raise self.error


def cliente_con(error: Exception) -> TestClient:
    app = crear_app()
    app.dependency_overrides[rutas.proveedor] = lambda: ProveedorQueFalla(error)
    token = create_access_token({"sub": "recepcion@marea.test", "role": "recepcionista"})
    return TestClient(app, raise_server_exceptions=False, headers={"Authorization": f"Bearer {token}"})


RESERVA = {"id_huesped": 1, "id_tipo": 2, "fecha_entrada": "2026-12-20", "fecha_salida": "2026-12-23", "numero_personas": 3}


def test_base_no_disponible_503_controlado():
    c = cliente_con(BaseNoDisponibleError("sin conexión"))
    r = c.post("/api/reservas", json=RESERVA)
    assert r.status_code == 503 and r.json()["codigo"] == "BD_NO_DISPONIBLE"
    assert c.get("/api/reservas/1").status_code == 503


def test_fallo_inesperado_500_sin_detalles_tecnicos(caplog):
    c = cliente_con(KeyError("campo_interno_secreto"))
    r = c.get("/api/reservas/1")
    assert r.status_code == 500
    assert r.json() == {"detail": "Ocurrió un error interno. Intente de nuevo más tarde.", "codigo": "ERROR_INTERNO"}
    assert "campo_interno_secreto" not in r.text
    assert "campo_interno_secreto" in caplog.text  # sí queda registrado en el servidor


def test_cors_permite_el_origen_de_vite():
    c = cliente_con(BaseNoDisponibleError("x"))
    r = c.options(
        "/api/reservas",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "Content-Type"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
