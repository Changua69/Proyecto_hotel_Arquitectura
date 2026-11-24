"""Endpoints del panel del personal, gestión de reservas, administración y reportes (semana 15).

| Método y ruta                               | Quién                       |
|---------------------------------------------|-----------------------------|
| GET    /api/panel/resumen                   | recepcionista, admin        |
| GET    /api/reservas?estado&desde&hasta     | personal: todas; huésped: solo las suyas |
| POST   /api/reservas/{id}/cancelar          | personal; huésped: las suyas (CONFIRMADAS)  |
| POST   /api/reservas/{id}/checkin · checkout | recepcionista, admin        |
| GET    /api/reportes/ventas?desde&hasta     | admin (JSON para la pantalla) |
| GET    /api/reportes/ventas.pdf?desde&hasta | admin (descarga en PDF)     |
| GET/POST /api/admin/usuarios                | admin                       |
| PUT    /api/admin/usuarios/{email}/rol      | admin                       |
| DELETE /api/admin/usuarios/{email}          | admin                       |
| GET    /api/admin/tipos, PUT /api/admin/tipos/{id} | admin                |
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.esquemas import ErrorSalida, dinero
from app.api.seguridad import ROLES_PERSONAL, Usuario, requiere_rol, usuario_actual
from app.persistence.proveedor import MongoProveedor, ProveedorRepositorios
from app.services.gestion import (
    AdministracionService,
    GestionReservasService,
    PanelService,
    ReporteVentasService,
)
from app.services.errores import SinPermisoError
from app.services.huespedes import GestionHuespedesService

router = APIRouter(prefix="/api", tags=["Panel, administración y reportes (semana 15)"])
personal = requiere_rol(*ROLES_PERSONAL)
solo_admin = requiere_rol("admin")


def proveedor() -> ProveedorRepositorios:
    return MongoProveedor()


def repo_usuarios():
    from app.persistence.usuarios import MongoUsuarioRepository

    return MongoUsuarioRepository()


def _hash(clave: str) -> str:
    from passlib.context import CryptContext

    return CryptContext(schemes=["bcrypt"], deprecated="auto").hash(clave)


def servicio_admin(p: ProveedorRepositorios = Depends(proveedor), u=Depends(repo_usuarios)) -> AdministracionService:
    return AdministracionService(u, p, _hash)


def _errores(*codigos: int) -> dict:
    return {c: {"model": ErrorSalida} for c in codigos}


# ------------------------------------------------------------------ esquemas de salida
class ReservaFilaSalida(BaseModel):
    id_reserva: int
    estado: str
    fecha_entrada: date
    fecha_salida: date
    noches: int
    numero_personas: int
    tarifa_noche: int | float
    total: int | float
    id_huesped: int
    huesped: str
    habitacion: str
    tipo: str

    @classmethod
    def desde(cls, f) -> "ReservaFilaSalida":
        return cls(id_reserva=f.id_reserva, estado=f.estado, fecha_entrada=f.fecha_entrada, fecha_salida=f.fecha_salida,
                   noches=f.noches, numero_personas=f.numero_personas, tarifa_noche=dinero(f.tarifa_noche),
                   total=dinero(f.total), id_huesped=f.id_huesped, huesped=f.huesped, habitacion=f.habitacion, tipo=f.tipo)


class ResumenSalida(BaseModel):
    fecha: date
    huespedes: int
    habitaciones: int
    ocupadas_hoy: int
    ocupacion_pct: float
    reservas_activas: int
    llegadas_hoy: int
    ventas_mes: int | float
    reservas_mes: int
    proximas_llegadas: list[ReservaFilaSalida]


class LineaSalida(BaseModel):
    grupo: str
    reservas: int
    noches: int
    total: int | float


class ReporteSalida(BaseModel):
    desde: date
    hasta: date
    generado: date
    total: int | float
    reservas_vendidas: int
    noches: int
    canceladas: int
    por_tipo: list[LineaSalida]
    por_estado: list[LineaSalida]
    reservas: list[ReservaFilaSalida]


class UsuarioSalida(BaseModel):
    email: str
    nombre: str
    rol: str


class UsuarioEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {
        "email": "recepcion2@marea.test", "nombre": "Recepción turno noche", "rol": "recepcionista", "clave": "UnaClaveSegura1"}})
    email: str = Field(max_length=200)
    nombre: str = Field(max_length=200)
    rol: str = Field(max_length=20)
    clave: str = Field(max_length=200)


class RolEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rol: str = Field(max_length=20)


class TipoSalida(BaseModel):
    id_tipo: int
    nombre: str
    capacidad_max: int
    tarifa_noche: int | float


class TipoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"capacidad_max": 4, "tarifa_noche": 210000}})
    capacidad_max: int
    tarifa_noche: Decimal


def _tipo(t) -> TipoSalida:
    return TipoSalida(id_tipo=t.id_tipo, nombre=t.nombre, capacidad_max=t.capacidad_max, tarifa_noche=dinero(t.tarifa_noche))


# ------------------------------------------------------------------ panel
@router.get("/panel/resumen", response_model=ResumenSalida, summary="Indicadores del dashboard general",
            responses=_errores(401, 403, 503))
def resumen(_: Usuario = Depends(personal), p: ProveedorRepositorios = Depends(proveedor)):
    r = PanelService(p).resumen()
    return ResumenSalida(fecha=r.fecha, huespedes=r.huespedes, habitaciones=r.habitaciones, ocupadas_hoy=r.ocupadas_hoy,
                         ocupacion_pct=r.ocupacion_pct, reservas_activas=r.reservas_activas, llegadas_hoy=r.llegadas_hoy,
                         ventas_mes=dinero(r.ventas_mes), reservas_mes=r.reservas_mes,
                         proximas_llegadas=[ReservaFilaSalida.desde(f) for f in r.proximas_llegadas])


# ------------------------------------------------------------------ reservas
@router.get("/reservas", response_model=list[ReservaFilaSalida], summary="Listar reservas (filtros opcionales)",
            responses=_errores(400, 401, 403, 503))
def listar_reservas(
    estado: str | None = Query(default=None, description="CONFIRMADA, EN_CURSO, FINALIZADA o CANCELADA"),
    desde: date | None = Query(default=None, description="Entrada desde (AAAA-MM-DD)"),
    hasta: date | None = Query(default=None, description="Entrada hasta (AAAA-MM-DD)"),
    usuario: Usuario = Depends(usuario_actual),
    p: ProveedorRepositorios = Depends(proveedor),
):
    id_huesped = None
    if not usuario.es_personal:  # un huésped solo ve las suyas
        ficha = GestionHuespedesService(p).obtener_por_correo(usuario.correo)
        if ficha is None:
            return []
        id_huesped = ficha.id_huesped
    filas = GestionReservasService(p).listar(estado, desde, hasta, id_huesped)
    return [ReservaFilaSalida.desde(f) for f in filas]


@router.post("/reservas/{id_reserva}/cancelar", status_code=204, summary="Cancelar una reserva CONFIRMADA",
             responses=_errores(400, 401, 403, 404, 409, 503))
def cancelar(id_reserva: int = Path(gt=0), usuario: Usuario = Depends(usuario_actual),
             p: ProveedorRepositorios = Depends(proveedor)):
    """Personal: cualquier reserva CONFIRMADA. Huésped: solo las suyas, mientras sigan CONFIRMADAS."""
    solo_de = None
    if not usuario.es_personal:
        ficha = GestionHuespedesService(p).obtener_por_correo(usuario.correo)
        if ficha is None:
            raise SinPermisoError("Su cuenta no está asociada a un huésped registrado.")
        solo_de = ficha.id_huesped
    GestionReservasService(p).cancelar(id_reserva, solo_de)
    return Response(status_code=204)


@router.post("/reservas/{id_reserva}/checkin", status_code=204, summary="Check-in: llegada del huésped",
             responses=_errores(400, 401, 403, 404, 409, 503))
def check_in(id_reserva: int = Path(gt=0), _: Usuario = Depends(personal), p: ProveedorRepositorios = Depends(proveedor)):
    GestionReservasService(p).check_in(id_reserva)
    return Response(status_code=204)


@router.post("/reservas/{id_reserva}/checkout", status_code=204, summary="Check-out: salida del huésped",
             responses=_errores(400, 401, 403, 404, 409, 503))
def check_out(id_reserva: int = Path(gt=0), _: Usuario = Depends(personal), p: ProveedorRepositorios = Depends(proveedor)):
    GestionReservasService(p).check_out(id_reserva)
    return Response(status_code=204)


# ------------------------------------------------------------------ reportes
def _reporte(desde: date, hasta: date, p: ProveedorRepositorios):
    return ReporteVentasService(p).generar(desde, hasta)


@router.get("/reportes/ventas", response_model=ReporteSalida, summary="Reporte de ventas (vista previa)",
            responses=_errores(400, 401, 403, 503))
def reporte_json(desde: date = Query(description="AAAA-MM-DD"), hasta: date = Query(description="AAAA-MM-DD"),
                 _: Usuario = Depends(solo_admin), p: ProveedorRepositorios = Depends(proveedor)):
    r = _reporte(desde, hasta, p)
    linea = lambda l: LineaSalida(grupo=l.grupo, reservas=l.reservas, noches=l.noches, total=dinero(l.total))  # noqa: E731
    return ReporteSalida(desde=r.desde, hasta=r.hasta, generado=r.generado, total=dinero(r.total),
                         reservas_vendidas=len(r.reservas), noches=r.noches, canceladas=r.canceladas,
                         por_tipo=[linea(l) for l in r.por_tipo], por_estado=[linea(l) for l in r.por_estado],
                         reservas=[ReservaFilaSalida.desde(f) for f in r.reservas])


@router.get("/reportes/ventas.pdf", summary="Reporte de ventas en PDF (descarga)",
            response_class=Response, responses={200: {"content": {"application/pdf": {}}}, **_errores(400, 401, 403, 503)})
def reporte_pdf(desde: date = Query(description="AAAA-MM-DD"), hasta: date = Query(description="AAAA-MM-DD"),
                _: Usuario = Depends(solo_admin), p: ProveedorRepositorios = Depends(proveedor)):
    from app.api.reporte_pdf import generar_pdf

    contenido = generar_pdf(_reporte(desde, hasta, p))
    nombre = f"reporte_ventas_{desde.isoformat()}_{hasta.isoformat()}.pdf"
    return Response(content=contenido, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


# ------------------------------------------------------------------ administración
@router.get("/admin/usuarios", response_model=list[UsuarioSalida], summary="Listar cuentas",
            responses=_errores(401, 403, 503))
def listar_usuarios(_: Usuario = Depends(solo_admin), s: AdministracionService = Depends(servicio_admin)):
    return [UsuarioSalida(email=u.email, nombre=u.nombre, rol=u.rol) for u in s.listar_usuarios()]


@router.post("/admin/usuarios", response_model=UsuarioSalida, status_code=201, summary="Crear cuenta con rol",
             responses=_errores(400, 401, 403, 409, 503))
def crear_usuario(entrada: UsuarioEntrada, _: Usuario = Depends(solo_admin), s: AdministracionService = Depends(servicio_admin)):
    u = s.crear_usuario(entrada.email, entrada.nombre, entrada.rol, entrada.clave)
    return UsuarioSalida(email=u.email, nombre=u.nombre, rol=u.rol)


@router.put("/admin/usuarios/{email}/rol", response_model=UsuarioSalida, summary="Cambiar el rol de una cuenta",
            responses=_errores(400, 401, 403, 404, 409, 503))
def cambiar_rol(entrada: RolEntrada, email: str = Path(max_length=200),
                actor: Usuario = Depends(solo_admin), s: AdministracionService = Depends(servicio_admin)):
    u = s.cambiar_rol(actor.correo, email, entrada.rol)
    return UsuarioSalida(email=u.email, nombre=u.nombre, rol=u.rol)


@router.delete("/admin/usuarios/{email}", status_code=204, summary="Eliminar una cuenta",
               responses=_errores(401, 403, 404, 409, 503))
def eliminar_usuario(email: str = Path(max_length=200), actor: Usuario = Depends(solo_admin),
                     s: AdministracionService = Depends(servicio_admin)):
    s.eliminar_usuario(actor.correo, email)
    return Response(status_code=204)


@router.get("/admin/tipos", response_model=list[TipoSalida], summary="Tipos de habitación y tarifas",
            responses=_errores(401, 403, 503))
def listar_tipos(_: Usuario = Depends(personal), s: AdministracionService = Depends(servicio_admin)):
    return [_tipo(t) for t in s.listar_tipos()]


@router.put("/admin/tipos/{id_tipo}", response_model=TipoSalida, summary="Actualizar capacidad y tarifa de un tipo",
            responses=_errores(400, 401, 403, 404, 503))
def actualizar_tipo(entrada: TipoEntrada, id_tipo: int = Path(gt=0),
                    _: Usuario = Depends(solo_admin), s: AdministracionService = Depends(servicio_admin)):
    return _tipo(s.actualizar_tipo(id_tipo, entrada.capacidad_max, entrada.tarifa_noche))
