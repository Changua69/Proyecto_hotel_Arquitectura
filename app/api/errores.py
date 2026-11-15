"""Manejo centralizado de errores de la API del corte (semana 14).

- Errores de negocio  -> su HTTP (400/404/409/422) con {"detail", "codigo"}.
- Entrada inválida    -> 400 DATOS_INVALIDOS (FastAPI usaría 422, pero 422 ya significa
                         CAPACIDAD_EXCEDIDA en nuestro contrato; así se distinguen).
- Base no disponible  -> 503 BD_NO_DISPONIBLE.
- Cualquier otro fallo -> 500 ERROR_INTERNO: se registra en el servidor con todo el detalle
                         y al cliente solo se le envía un mensaje genérico.
Solo aplica a rutas /api; las rutas heredadas conservan el comportamiento de FastAPI.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.persistence.errors import BaseNoDisponibleError, PersistenciaError
from app.services.errores import ErrorNegocio

log = logging.getLogger("marea.api")

_MENSAJES = {
    "missing": "es obligatorio",
    "int_parsing": "debe ser un número entero",
    "int_type": "debe ser un número entero",
    "int_from_float": "debe ser un número entero",
    "date_parsing": "debe ser una fecha con formato AAAA-MM-DD",
    "date_from_datetime_parsing": "debe ser una fecha con formato AAAA-MM-DD",
    "date_type": "debe ser una fecha con formato AAAA-MM-DD",
    "extra_forbidden": "no es un campo permitido",
    "json_invalid": "el cuerpo no es un JSON válido",
    "model_attributes_type": "el cuerpo debe ser un objeto JSON",
    "dict_type": "el cuerpo debe ser un objeto JSON",
}


def _mensaje(err: dict) -> str:
    tipo = err.get("type", "")
    ctx = err.get("ctx") or {}
    if tipo == "greater_than":
        return f"debe ser mayor que {ctx.get('gt')}"
    if tipo == "greater_than_equal":
        return f"debe ser mayor o igual que {ctx.get('ge')}"
    return _MENSAJES.get(tipo, err.get("msg", "valor inválido"))


def _campo(err: dict) -> str:
    loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
    return ".".join(loc) or "cuerpo"


def _es_api(request: Request) -> bool:
    return request.url.path.startswith("/api")


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorNegocio)
    async def _negocio(request: Request, exc: ErrorNegocio):
        return JSONResponse(status_code=exc.http, content={"detail": exc.mensaje, "codigo": exc.codigo})

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError):
        if not _es_api(request):
            return await request_validation_exception_handler(request, exc)
        errores = [{"campo": _campo(e), "mensaje": _mensaje(e)} for e in exc.errors()]
        resumen = "; ".join(f"{e['campo']}: {e['mensaje']}" for e in errores)
        return JSONResponse(
            status_code=400,
            content={"detail": f"Datos de entrada inválidos. {resumen}", "codigo": "DATOS_INVALIDOS", "errores": errores},
        )

    @app.exception_handler(BaseNoDisponibleError)
    @app.exception_handler(PersistenciaError)
    async def _bd(request: Request, exc: Exception):
        log.error("Base de datos no disponible: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "La base de datos no está disponible. Intente de nuevo más tarde.", "codigo": "BD_NO_DISPONIBLE"},
        )

    @app.exception_handler(Exception)
    async def _interno(request: Request, exc: Exception):
        log.exception("Error interno en %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Ocurrió un error interno. Intente de nuevo más tarde.", "codigo": "ERROR_INTERNO"},
        )
