"""Endpoints del corte vertical (semana 14).

Cada endpoint recibe HTTP, construye la solicitud del servicio y traduce la respuesta.
No contiene reglas de negocio ni acceso a MongoDB.

| RF    | Método y ruta                 | Servicio                       |
|-------|-------------------------------|--------------------------------|
| RF-02 | GET  /api/disponibilidad      | ConsultarDisponibilidadService |
| RF-04 | POST /api/reservas            | RegistrarReservaService        |
| RF-04 | GET  /api/reservas/{id}       | ConsultarReservaService        |

Permisos (semana 15): consultar disponibilidad es público. Crear y consultar reservas exige
iniciar sesión; recepcionista y admin trabajan con cualquier huésped, y un huésped solo con
su propia ficha (la que tiene el mismo correo de su cuenta).
"""
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Response

from app.api.esquemas import DisponibilidadSalida, ErrorSalida, ReservaCambio, ReservaEntrada, ReservaSalida
from app.api.seguridad import Usuario, usuario_actual
from app.persistence.config import nombre_base
from app.persistence.proveedor import MongoProveedor, ProveedorRepositorios, comprobar_conexion
from app.services.errores import SinPermisoError
from app.services.huespedes import GestionHuespedesService
from app.services.reservas import (
    CambioReserva,
    ConsultarDisponibilidadService,
    ModificarReservaService,
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


def _exigir_propio(usuario: Usuario, id_huesped: int, p: ProveedorRepositorios) -> None:
    """Validación recepcionista -> huésped: el personal opera para cualquier huésped;
    un huésped solo para sí mismo."""
    if usuario.es_personal:
        return
    ficha = GestionHuespedesService(p).obtener_por_correo(usuario.correo)
    if ficha is None:
        raise SinPermisoError("Su cuenta no está asociada a un huésped registrado. Acérquese a recepción.")
    if ficha.id_huesped != id_huesped:
        raise SinPermisoError("Solo puede gestionar sus propias reservas.")


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
    responses=_errores(400, 401, 403, 404, 409, 422, 503),
)
def crear_reserva(
    entrada: ReservaEntrada,
    response: Response,
    usuario: Usuario = Depends(usuario_actual),
    p: ProveedorRepositorios = Depends(proveedor),
    servicio: RegistrarReservaService = Depends(servicio_registro),
):
    _exigir_propio(usuario, entrada.id_huesped, p)
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
    responses=_errores(400, 401, 403, 404, 503),
)
def consultar_reserva(
    id_reserva: int = Path(gt=0, description="Entero positivo"),
    usuario: Usuario = Depends(usuario_actual),
    p: ProveedorRepositorios = Depends(proveedor),
    servicio: ConsultarReservaService = Depends(servicio_consulta),
):
    detalle = servicio.consultar(id_reserva)
    _exigir_propio(usuario, detalle.huesped.id_huesped, p)
    return ReservaSalida.desde(detalle)


@router.put(
    "/reservas/{id_reserva}",
    response_model=ReservaSalida,
    summary="Modificar fechas o personas de una reserva CONFIRMADA",
    description="Mismo tipo de habitación. Conserva la habitación si sigue libre; si no, asigna otra del "
    "mismo tipo. Se mantiene la tarifa por noche acordada y se recalcula el total. Personal: cualquier "
    "reserva; huésped: solo las suyas y hasta el día anterior a la llegada.",
    responses=_errores(400, 401, 403, 404, 409, 422, 503),
)
def modificar_reserva(
    cambio: ReservaCambio,
    id_reserva: int = Path(gt=0, description="Entero positivo"),
    usuario: Usuario = Depends(usuario_actual),
    p: ProveedorRepositorios = Depends(proveedor),
):
    solo_de = None
    if not usuario.es_personal:
        ficha = GestionHuespedesService(p).obtener_por_correo(usuario.correo)
        if ficha is None:
            raise SinPermisoError("Su cuenta no está asociada a un huésped registrado. Acérquese a recepción.")
        solo_de = ficha.id_huesped
    detalle = ModificarReservaService(p).modificar(
        id_reserva, CambioReserva(cambio.fecha_entrada, cambio.fecha_salida, cambio.numero_personas), solo_de)
    return ReservaSalida.desde(detalle)


# ------------------------------------------------------------------ estado
@router.get("/salud", summary="Estado de la API y de la base", responses=_errores(503))
def salud():
    comprobar_conexion()  # 503 BD_NO_DISPONIBLE si MongoDB no responde
    return {"estado": "ok", "base": nombre_base()}
