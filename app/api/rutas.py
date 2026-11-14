"""Endpoints del corte vertical (semana 14).

Cada endpoint recibe HTTP, construye la solicitud del servicio y traduce la respuesta.
No contiene reglas de negocio ni acceso a MongoDB.

| RF    | Método y ruta                 | Servicio                       |
|-------|-------------------------------|--------------------------------|
| RF-02 | GET  /api/disponibilidad      | ConsultarDisponibilidadService |
| RF-04 | POST /api/reservas            | RegistrarReservaService        |
| RF-04 | GET  /api/reservas/{id}       | ConsultarReservaService        |
"""
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Response

from app.api.esquemas import DisponibilidadSalida, ErrorSalida, ReservaEntrada, ReservaSalida
from app.persistence.proveedor import MongoProveedor, ProveedorRepositorios
from app.services.reservas import (
    ConsultarDisponibilidadService,
    ConsultarReservaService,
    RegistrarReservaService,
    SolicitudDisponibilidad,
    SolicitudReserva,
)

router = APIRouter(prefix="/api", tags=["Corte vertical: Crear una reserva"])


# ------------------------------------------------------------------ dependencias
def proveedor() -> ProveedorRepositorios:
    return MongoProveedor()


def servicio_disponibilidad(p: ProveedorRepositorios = Depends(proveedor)) -> ConsultarDisponibilidadService:
    return ConsultarDisponibilidadService(p)


def servicio_registro(p: ProveedorRepositorios = Depends(proveedor)) -> RegistrarReservaService:
    return RegistrarReservaService(p)


def servicio_consulta(p: ProveedorRepositorios = Depends(proveedor)) -> ConsultarReservaService:
    return ConsultarReservaService(p)


def _errores(*codigos: int) -> dict:
    return {c: {"model": ErrorSalida} for c in codigos}


# ------------------------------------------------------------------ RF-02
@router.get(
    "/disponibilidad",
    response_model=DisponibilidadSalida,
    summary="RF-02. Consultar disponibilidad",
    description="Habitaciones del tipo sin reservas activas que se crucen con [fecha_entrada, fecha_salida). "
    "Si no hay, responde 200 con la lista vacía.",
    responses=_errores(400, 404, 422, 503),
)
def consultar_disponibilidad(
    id_tipo: int = Query(gt=0, description="1 Estándar, 2 Familiar, 3 Suite"),
    fecha_entrada: date = Query(description="AAAA-MM-DD"),
    fecha_salida: date = Query(description="AAAA-MM-DD"),
    personas: int = Query(ge=1),
    servicio: ConsultarDisponibilidadService = Depends(servicio_disponibilidad),
):
    resultado = servicio.consultar(SolicitudDisponibilidad(id_tipo, fecha_entrada, fecha_salida, personas))
    return DisponibilidadSalida.desde(resultado)


# ------------------------------------------------------------------ RF-04
@router.post(
    "/reservas",
    response_model=ReservaSalida,
    status_code=201,
    summary="RF-04. Crear reserva",
    description="Asigna la habitación libre de menor número del tipo, calcula el total y guarda la reserva "
    "CONFIRMADA. Responde 201 solo después de confirmar la escritura.",
    responses=_errores(400, 404, 409, 422, 503),
)
def crear_reserva(
    entrada: ReservaEntrada,
    response: Response,
    servicio: RegistrarReservaService = Depends(servicio_registro),
):
    detalle = servicio.registrar(
        SolicitudReserva(
            id_huesped=entrada.id_huesped,
            id_tipo=entrada.id_tipo,
            fecha_entrada=entrada.fecha_entrada,
            fecha_salida=entrada.fecha_salida,
            numero_personas=entrada.numero_personas,
        )
    )
    response.headers["Location"] = f"/api/reservas/{detalle.reserva.id_reserva}"
    return ReservaSalida.desde(detalle)


@router.get(
    "/reservas/{id_reserva}",
    response_model=ReservaSalida,
    summary="RF-04 (confirmación). Consultar una reserva por id",
    description="Recupera una reserva guardada. Sirve para confirmarla y para verificar si una "
    "creación quedó guardada antes de repetirla.",
    responses=_errores(400, 404, 503),
)
def consultar_reserva(
    id_reserva: int = Path(gt=0, description="Entero positivo"),
    servicio: ConsultarReservaService = Depends(servicio_consulta),
):
    return ReservaSalida.desde(servicio.consultar(id_reserva))
