"""Endpoints del CRUD de huéspedes (semana 15).

| Método y ruta                  | Quién puede                              | Respuestas            |
|--------------------------------|------------------------------------------|-----------------------|
| GET    /api/huespedes?buscar=  | recepcionista, admin                     | 200                   |
| GET    /api/huespedes/yo       | huésped (su propia ficha, por su correo) | 200, 404              |
| POST   /api/huespedes/yo       | huésped sin ficha (completa sus datos)   | 201, 400, 409         |
| GET    /api/huespedes/{id}     | recepcionista, admin; huésped solo la suya | 200, 403, 404       |
| POST   /api/huespedes          | recepcionista, admin                     | 201, 400, 409         |
| PUT    /api/huespedes/{id}     | recepcionista, admin                     | 200, 400, 404, 409    |
| DELETE /api/huespedes/{id}     | admin                                    | 204, 404, 409         |

Todas exigen token (401 NO_AUTENTICADO) y responden 403 SIN_PERMISO si el rol no alcanza.
Interfaz -> API (este archivo) -> GestionHuespedesService -> MongoHuespedRepository -> MongoDB.
"""
from fastapi import APIRouter, Depends, Path, Query, Response

from app.api.esquemas import ErrorSalida, HuespedEntrada, HuespedSalida, MiFichaEntrada
from app.api.seguridad import ROLES_PERSONAL, Usuario, requiere_rol, usuario_actual
from app.persistence.proveedor import MongoProveedor, ProveedorRepositorios
from app.services.errores import DatoDuplicadoError, NoEncontradoError, SinPermisoError
from app.services.huespedes import DatosHuesped, GestionHuespedesService

router = APIRouter(prefix="/api/huespedes", tags=["Huéspedes (CRUD, semana 15)"])


def proveedor() -> ProveedorRepositorios:
    return MongoProveedor()


def servicio(p: ProveedorRepositorios = Depends(proveedor)) -> GestionHuespedesService:
    return GestionHuespedesService(p)


def _errores(*codigos: int) -> dict:
    return {c: {"model": ErrorSalida} for c in codigos}


def _datos(e: HuespedEntrada) -> DatosHuesped:
    return DatosHuesped(e.nombre, e.documento, e.nacionalidad, e.telefono, e.correo)


personal = requiere_rol(*ROLES_PERSONAL)
solo_admin = requiere_rol("admin")


@router.get("", response_model=list[HuespedSalida], summary="Listar huéspedes (filtro opcional)",
            responses=_errores(400, 401, 403, 503))
def listar(
    buscar: str | None = Query(default=None, description="Texto en nombre, documento o correo"),
    _: Usuario = Depends(personal),
    s: GestionHuespedesService = Depends(servicio),
):
    return [HuespedSalida.desde(h) for h in s.listar(buscar)]


@router.get("/yo", response_model=HuespedSalida, summary="Ficha del huésped que inició sesión",
            responses=_errores(401, 404, 503))
def mi_ficha(usuario: Usuario = Depends(usuario_actual), s: GestionHuespedesService = Depends(servicio)):
    h = s.obtener_por_correo(usuario.correo)
    if h is None:
        raise NoEncontradoError("Su cuenta no está asociada a ningún huésped registrado.")
    return HuespedSalida.desde(h)


@router.post("/yo", response_model=HuespedSalida, status_code=201, summary="Completar mi ficha (huésped)",
             responses=_errores(400, 401, 403, 409, 503))
def crear_mi_ficha(entrada: MiFichaEntrada, usuario: Usuario = Depends(usuario_actual),
                   s: GestionHuespedesService = Depends(servicio)):
    """Para cuentas de huésped creadas antes de que el registro creara la ficha."""
    if usuario.es_personal:
        raise SinPermisoError("Esta opción es solo para cuentas de huésped.")
    if s.obtener_por_correo(usuario.correo):
        raise DatoDuplicadoError("Su cuenta ya tiene sus datos registrados.")
    h = s.asegurar_ficha_propia(usuario.correo, entrada.nombre, entrada.documento, entrada.telefono, entrada.nacionalidad)
    return HuespedSalida.desde(h)


@router.get("/{id_huesped}", response_model=HuespedSalida, summary="Consultar un huésped por id",
            responses=_errores(400, 401, 403, 404, 503))
def obtener(
    id_huesped: int = Path(gt=0),
    usuario: Usuario = Depends(usuario_actual),
    s: GestionHuespedesService = Depends(servicio),
):
    h = s.obtener(id_huesped)
    # Validación recepcionista -> huésped: el personal ve cualquier ficha; un huésped solo la suya.
    if not usuario.es_personal and (h.correo or "").lower() != usuario.correo:
        raise SinPermisoError("Solo puede consultar sus propios datos.")
    return HuespedSalida.desde(h)


@router.post("", response_model=HuespedSalida, status_code=201, summary="Registrar huésped",
             responses=_errores(400, 401, 403, 409, 503))
def crear(entrada: HuespedEntrada, response: Response,
          _: Usuario = Depends(personal), s: GestionHuespedesService = Depends(servicio)):
    h = s.crear(_datos(entrada))
    response.headers["Location"] = f"/api/huespedes/{h.id_huesped}"
    return HuespedSalida.desde(h)


@router.put("/{id_huesped}", response_model=HuespedSalida, summary="Actualizar huésped",
            responses=_errores(400, 401, 403, 404, 409, 503))
def actualizar(entrada: HuespedEntrada, id_huesped: int = Path(gt=0),
               _: Usuario = Depends(personal), s: GestionHuespedesService = Depends(servicio)):
    return HuespedSalida.desde(s.actualizar(id_huesped, _datos(entrada)))


@router.delete("/{id_huesped}", status_code=204, summary="Eliminar huésped (solo admin)",
               responses=_errores(400, 401, 403, 404, 409, 503))
def eliminar(id_huesped: int = Path(gt=0),
             _: Usuario = Depends(solo_admin), s: GestionHuespedesService = Depends(servicio)):
    s.eliminar(id_huesped)
    return Response(status_code=204)
