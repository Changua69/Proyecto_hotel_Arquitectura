"""Servicios del panel del personal, la administración y el reporte de ventas (semana 15).

Igual que en el corte: el servicio decide las reglas, los repositorios consultan/guardan y
la API solo traduce HTTP. Nada aquí conoce MongoDB.
"""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

from app.persistence.errors import DatosInvalidosError as DatosRechazadosPorBD
from app.persistence.errors import DuplicadoError
from app.persistence.models import ReservaFila, TipoHabitacion, Usuario
from app.persistence.proveedor import ProveedorRepositorios
from app.services.errores import (
    DatoDuplicadoError,
    EntradaInvalidaError,
    ErrorNegocio,
    EstadoReservaError,
    FechasInvalidasError,
    NoEncontradoError,
    SinPermisoError,
)

Reloj = Callable[[], date]
ESTADOS_RESERVA = ("CONFIRMADA", "EN_CURSO", "FINALIZADA", "CANCELADA")
ESTADOS_ACTIVOS = ["CONFIRMADA", "EN_CURSO"]
ROLES = ("huesped", "recepcionista", "admin")
MAX_DIAS_REPORTE = 366


class ReservaNoCancelableError(ErrorNegocio):
    """Solo se cancela una reserva CONFIRMADA (no una en curso, finalizada o ya cancelada)."""

    http = 409
    codigo = "RESERVA_NO_CANCELABLE"


class OperacionNoPermitidaError(ErrorNegocio):
    """Regla de administración: p. ej. quitarse a sí mismo el rol o dejar el sistema sin admin."""

    http = 409
    codigo = "OPERACION_NO_PERMITIDA"


def _rango(desde: date | None, hasta: date | None) -> None:
    if desde and hasta:
        if hasta < desde:
            raise FechasInvalidasError("La fecha 'hasta' no puede ser anterior a 'desde'.")
        if (hasta - desde).days > MAX_DIAS_REPORTE:
            raise FechasInvalidasError(f"El rango no puede superar {MAX_DIAS_REPORTE} días.")


def _id(valor: int, nombre: str) -> None:
    if not isinstance(valor, int) or valor <= 0:
        raise EntradaInvalidaError(f"El id de {nombre} debe ser un entero positivo.")


# ------------------------------------------------------------------ panel (dashboard general)
@dataclass(frozen=True)
class ResumenPanel:
    fecha: date
    huespedes: int
    habitaciones: int
    ocupadas_hoy: int
    reservas_activas: int
    llegadas_hoy: int
    ventas_mes: Decimal
    reservas_mes: int
    proximas_llegadas: list[ReservaFila]

    @property
    def ocupacion_pct(self) -> float:
        return round(100 * self.ocupadas_hoy / self.habitaciones, 1) if self.habitaciones else 0.0


class PanelService:
    def __init__(self, proveedor: ProveedorRepositorios, hoy: Reloj = date.today):
        self._p, self._hoy = proveedor, hoy

    def resumen(self) -> ResumenPanel:
        hoy = self._hoy()
        inicio_mes = hoy.replace(day=1)
        fin_mes = (inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        def caso(r) -> ResumenPanel:
            g = r.gestion
            mes = [f for f in g.listar_reservas(desde=inicio_mes, hasta=fin_mes) if f.estado != "CANCELADA"]
            proximas = [f for f in g.listar_reservas(desde=hoy, hasta=hoy + timedelta(days=14))
                        if f.estado in ESTADOS_ACTIVOS]
            proximas.sort(key=lambda f: (f.fecha_entrada, f.id_reserva))
            return ResumenPanel(
                fecha=hoy,
                huespedes=g.contar("huespedes"),
                habitaciones=g.contar("habitaciones"),
                ocupadas_hoy=g.ocupadas_en(hoy),
                reservas_activas=g.contar("reservas", ESTADOS_ACTIVOS),
                llegadas_hoy=sum(1 for f in proximas if f.fecha_entrada == hoy),
                ventas_mes=sum((f.total for f in mes), Decimal("0")),
                reservas_mes=len(mes),
                proximas_llegadas=proximas[:8],
            )

        return self._p.leer(caso)


# ------------------------------------------------------------------ reservas (gestión)
class GestionReservasService:
    def __init__(self, proveedor: ProveedorRepositorios, hoy: Reloj = date.today):
        self._p, self._hoy = proveedor, hoy

    def listar(self, estado: str | None = None, desde: date | None = None, hasta: date | None = None,
               id_huesped: int | None = None) -> list[ReservaFila]:
        if estado and estado not in ESTADOS_RESERVA:
            raise EntradaInvalidaError(f"Estado inválido. Use uno de: {', '.join(ESTADOS_RESERVA)}.", campo="estado")
        _rango(desde, hasta)
        return self._p.leer(lambda r: r.gestion.listar_reservas(estado, desde, hasta, id_huesped))

    def check_in(self, id_reserva: int) -> None:
        """Llegada del huésped: CONFIRMADA -> EN_CURSO (habitación OCUPADA).
        Solo desde el día de entrada y antes del día de salida."""
        _id(id_reserva, "la reserva")
        hoy = self._hoy()

        def caso(r):
            actual = r.reservas.buscar_por_id(id_reserva)
            if actual is None:
                raise NoEncontradoError("La reserva no existe.")
            if actual.estado != "CONFIRMADA":
                raise EstadoReservaError(f"La reserva está {actual.estado}; el check-in se hace a una CONFIRMADA.")
            if hoy < actual.fecha_entrada:
                raise EstadoReservaError(f"La llegada es el {actual.fecha_entrada.isoformat()}; todavía no se puede hacer check-in.")
            if hoy >= actual.fecha_salida:
                raise EstadoReservaError("La fecha de salida ya pasó; no se puede hacer check-in.")
            if not r.gestion.cambiar_estado_reserva(id_reserva, "CONFIRMADA", "EN_CURSO", "OCUPADA"):
                raise EstadoReservaError("La reserva cambió de estado; actualice e intente de nuevo.")

        self._p.escribir(caso)

    def check_out(self, id_reserva: int) -> None:
        """Salida del huésped: EN_CURSO -> FINALIZADA (habitación LIBRE).
        Si sale antes de la fecha prevista, las noches restantes quedan libres para otras reservas."""
        _id(id_reserva, "la reserva")

        def caso(r):
            actual = r.reservas.buscar_por_id(id_reserva)
            if actual is None:
                raise NoEncontradoError("La reserva no existe.")
            if actual.estado != "EN_CURSO":
                raise EstadoReservaError(f"La reserva está {actual.estado}; el check-out se hace a una EN CURSO.")
            if not r.gestion.cambiar_estado_reserva(id_reserva, "EN_CURSO", "FINALIZADA", "LIBRE"):
                raise EstadoReservaError("La reserva cambió de estado; actualice e intente de nuevo.")

        self._p.escribir(caso)

    def cancelar(self, id_reserva: int, solo_del_huesped: int | None = None) -> None:
        """Cancela una reserva CONFIRMADA (queda en el historial como CANCELADA; no se borra).

        `solo_del_huesped`: cuando cancela el propio huésped. Solo puede cancelar SUS reservas y hasta
        el día anterior a la llegada; el personal (None) no tiene esas restricciones.
        """
        _id(id_reserva, "la reserva")

        def caso(r):
            actual = r.reservas.buscar_por_id(id_reserva)
            if actual is None:
                raise NoEncontradoError("La reserva no existe.")
            if solo_del_huesped is not None:
                if actual.id_huesped != solo_del_huesped:
                    raise SinPermisoError("Solo puede cancelar sus propias reservas.")
                if actual.estado == "CONFIRMADA" and actual.fecha_entrada <= self._hoy():
                    raise ReservaNoCancelableError(
                        "Solo puede cancelar hasta el día anterior a la llegada. Comuníquese con recepción.")
            if not r.gestion.cancelar_reserva(id_reserva):
                raise ReservaNoCancelableError(f"La reserva está {actual.estado}; solo se cancela una CONFIRMADA.")

        self._p.escribir(caso)


# ------------------------------------------------------------------ reporte de ventas
@dataclass(frozen=True)
class LineaReporte:
    grupo: str
    reservas: int
    noches: int
    total: Decimal


@dataclass(frozen=True)
class ReporteVentas:
    desde: date
    hasta: date
    generado: date
    reservas: list[ReservaFila]          # sin canceladas
    canceladas: int
    por_tipo: list[LineaReporte] = field(default_factory=list)
    por_estado: list[LineaReporte] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((f.total for f in self.reservas), Decimal("0"))

    @property
    def noches(self) -> int:
        return sum(f.noches for f in self.reservas)


def _agrupar(filas: list[ReservaFila], clave) -> list[LineaReporte]:
    grupos: dict[str, list[ReservaFila]] = {}
    for f in filas:
        grupos.setdefault(clave(f), []).append(f)
    lineas = [LineaReporte(g, len(fs), sum(x.noches for x in fs), sum((x.total for x in fs), Decimal("0")))
              for g, fs in grupos.items()]
    return sorted(lineas, key=lambda l: (-l.total, l.grupo))


class ReporteVentasService:
    """Ventas = reservas NO canceladas cuya fecha de entrada está en [desde, hasta]."""

    def __init__(self, proveedor: ProveedorRepositorios, hoy: Reloj = date.today):
        self._p, self._hoy = proveedor, hoy

    def generar(self, desde: date, hasta: date) -> ReporteVentas:
        if desde is None or hasta is None:
            raise EntradaInvalidaError("Indique las fechas 'desde' y 'hasta' (AAAA-MM-DD).")
        _rango(desde, hasta)
        todas = self._p.leer(lambda r: r.gestion.listar_reservas(desde=desde, hasta=hasta, limite=5000))
        ventas = sorted((f for f in todas if f.estado != "CANCELADA"), key=lambda f: (f.fecha_entrada, f.id_reserva))
        return ReporteVentas(
            desde=desde, hasta=hasta, generado=self._hoy(), reservas=ventas,
            canceladas=sum(1 for f in todas if f.estado == "CANCELADA"),
            por_tipo=_agrupar(ventas, lambda f: f.tipo),
            por_estado=_agrupar(ventas, lambda f: f.estado),
        )


# ------------------------------------------------------------------ administración
_RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AdministracionService:
    """Usuarios y roles (repositorio de cuentas) + tarifas y capacidades de los tipos (proveedor del corte)."""

    def __init__(self, usuarios, proveedor: ProveedorRepositorios, hasher: Callable[[str], str]):
        self._u, self._p, self._hash = usuarios, proveedor, hasher

    # -------- usuarios
    def listar_usuarios(self) -> list[Usuario]:
        return self._u.listar()

    def crear_usuario(self, email: str, nombre: str, rol: str, clave: str) -> Usuario:
        email = (email or "").strip().lower()
        nombre = " ".join((nombre or "").split())
        errores = []
        if not _RE_CORREO.match(email) or len(email) > 120:
            errores.append({"campo": "email", "mensaje": "no tiene un formato válido"})
        if not 2 <= len(nombre) <= 100:
            errores.append({"campo": "nombre", "mensaje": "debe tener entre 2 y 100 caracteres"})
        if rol not in ROLES:
            errores.append({"campo": "rol", "mensaje": "debe ser huesped, recepcionista o admin"})
        if len(clave or "") < 8:
            errores.append({"campo": "clave", "mensaje": "debe tener al menos 8 caracteres"})
        if errores:
            raise EntradaInvalidaError("Datos de entrada inválidos. " + "; ".join(f"{e['campo']}: {e['mensaje']}" for e in errores),
                                       errores=errores)
        if self._u.obtener(email):
            raise DatoDuplicadoError("Ya existe una cuenta con ese correo.", campo="email")
        usuario = Usuario(email, nombre, rol)
        try:
            self._u.crear(usuario, self._hash(clave))
        except DuplicadoError as e:
            raise DatoDuplicadoError("Ya existe una cuenta con ese correo.", campo="email") from e
        return usuario

    def cambiar_rol(self, actor: str, email: str, rol: str) -> Usuario:
        email = (email or "").strip().lower()
        if rol not in ROLES:
            raise EntradaInvalidaError("Rol inválido: use huesped, recepcionista o admin.", campo="rol")
        actual = self._u.obtener(email)
        if actual is None:
            raise NoEncontradoError("La cuenta no existe.")
        if email == actor.lower() and rol != actual.rol:
            raise OperacionNoPermitidaError("No puede cambiar su propio rol.")
        if actual.rol == "admin" and rol != "admin" and self._u.contar_rol("admin") <= 1:
            raise OperacionNoPermitidaError("Debe quedar al menos un administrador.")
        self._u.cambiar_rol(email, rol)
        return Usuario(actual.email, actual.nombre, rol)

    def eliminar_usuario(self, actor: str, email: str) -> None:
        email = (email or "").strip().lower()
        if email == actor.lower():
            raise OperacionNoPermitidaError("No puede eliminar su propia cuenta.")
        actual = self._u.obtener(email)
        if actual is None:
            raise NoEncontradoError("La cuenta no existe.")
        if actual.rol == "admin" and self._u.contar_rol("admin") <= 1:
            raise OperacionNoPermitidaError("Debe quedar al menos un administrador.")
        self._u.eliminar(email)

    # -------- tipos de habitación (tarifas)
    def listar_tipos(self) -> list[TipoHabitacion]:
        return self._p.leer(lambda r: r.gestion.listar_tipos())

    def actualizar_tipo(self, id_tipo: int, capacidad_max: int, tarifa_noche: Decimal) -> TipoHabitacion:
        _id(id_tipo, "tipo")
        errores = []
        if not isinstance(capacidad_max, int) or not 1 <= capacidad_max <= 10:
            errores.append({"campo": "capacidad_max", "mensaje": "debe estar entre 1 y 10"})
        if tarifa_noche is None or tarifa_noche <= 0 or tarifa_noche > Decimal("100000000"):
            errores.append({"campo": "tarifa_noche", "mensaje": "debe ser mayor que 0"})
        if errores:
            raise EntradaInvalidaError("Datos de entrada inválidos. " + "; ".join(f"{e['campo']}: {e['mensaje']}" for e in errores),
                                       errores=errores)
        tarifa = Decimal(tarifa_noche).quantize(Decimal("0.01"))

        def caso(r):
            if not r.gestion.actualizar_tipo(id_tipo, capacidad_max, tarifa):
                raise NoEncontradoError("El tipo de habitación no existe.")
            return next(t for t in r.gestion.listar_tipos() if t.id_tipo == id_tipo)

        try:
            return self._p.escribir(caso)
        except DatosRechazadosPorBD as e:
            raise EntradaInvalidaError("La base de datos rechazó los datos del tipo.") from e
