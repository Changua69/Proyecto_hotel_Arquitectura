"""Aplicación FastAPI del corte vertical (semana 14).

Ejecutar:
    uvicorn app.api.app:app --reload --port 8000
Documentación interactiva de los contratos: http://127.0.0.1:8000/docs

Solo incluye las rutas del corte, sin las rutas heredadas (`app/main.py`), así que no necesita
las dependencias de autenticación ni la base `hotel_db`.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errores import registrar_manejadores
from app.api.rutas import router
from app.persistence.config import nombre_base
from app.persistence.proveedor import comprobar_conexion

ORIGENES_POR_DEFECTO = "http://localhost:5173,http://127.0.0.1:5173"  # Vite (pantalla de la semana 15)


def origenes_cors() -> list[str]:
    return [o.strip() for o in os.getenv("CORS_ORIGINS", ORIGENES_POR_DEFECTO).split(",") if o.strip()]


def registrar_corte(app: FastAPI) -> None:
    """Agrega las rutas y el manejo de errores del corte a una aplicación existente."""
    app.include_router(router)
    registrar_manejadores(app)


def crear_app() -> FastAPI:
    app = FastAPI(
        title="MareaDorada Pro — Corte vertical «Crear una reserva»",
        version="1.0 (semana 14)",
        description="RF-02 Consultar disponibilidad y RF-04 Crear reserva. "
        "Errores controlados con el formato {\"detail\": ..., \"codigo\": ...}.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes_cors(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["Location"],
    )
    registrar_corte(app)

    @app.get("/api/salud", tags=["Corte vertical: Crear una reserva"], summary="Estado de la API y de la base")
    def salud():
        comprobar_conexion()  # 503 BD_NO_DISPONIBLE si MongoDB no responde
        return {"estado": "ok", "base": nombre_base()}

    _openapi_sin_422_por_defecto(app)
    return app


def _openapi_sin_422_por_defecto(app: FastAPI) -> None:
    """FastAPI documenta por su cuenta un 422 de validación en cada ruta, pero nuestra API
    responde 400 DATOS_INVALIDOS en ese caso. Se quita ese 422 automático de /docs para que el
    contrato publicado coincida con el comportamiento real (el 422 propio, CAPACIDAD_EXCEDIDA, se conserva)."""
    original = app.openapi

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        esquema = original()
        for operaciones in esquema.get("paths", {}).values():
            for op in operaciones.values():
                r422 = op.get("responses", {}).get("422", {})
                ref = r422.get("content", {}).get("application/json", {}).get("schema", {}).get("$ref", "")
                if ref.endswith("/HTTPValidationError"):
                    del op["responses"]["422"]
        app.openapi_schema = esquema
        return esquema

    app.openapi = openapi


app = crear_app()
