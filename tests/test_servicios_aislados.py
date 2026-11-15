"""RNF-06 — Mantenibilidad / capacidad para ser probado (semana 14).

Los servicios de RF-02 y RF-04 se prueban con repositorios SIMULADOS en memoria.
Ninguna prueba abre una conexión real: el conftest bloquea pymongo.MongoClient para
las pruebas marcadas `sin_base`. Los dobles registran las llamadas para comprobar, por
ejemplo, que en un rechazo NO se invoca `guardar` y que una consulta solo lee.

Ejecutar solo estas:  pytest -v -m sin_base
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.persistence.errors import SolapeReservaError
from app.persistence.models import Habitacion, Huesped, NuevaReserva, Reserva, TipoHabitacion
from app.persistence.proveedor import Repositorios
from app.services.errores import (
    CapacidadExcedidaError,
    EntradaInvalidaError,
    FechasInvalidasError,
    NoEncontradoError,
    SinDisponibilidadError,
)
from app.services.reservas import (
    ConsultarDisponibilidadService,
    ConsultarReservaService,
    RegistrarReservaService,
    SolicitudDisponibilidad,
    SolicitudReserva,
)

pytestmark = pytest.mark.sin_base

HOY = date(2026, 11, 14)
D = date


# ------------------------------------------------------------------ dobles en memoria
@dataclass
class Registro:
    llamadas: list[str] = field(default_factory=list)

    def anotar(self, nombre: str) -> None:
        self.llamadas.append(nombre)


class TiposFalsos:
    def __init__(self, reg: Registro):
        self.reg = reg
        self.datos = {
            1: TipoHabitacion(1, "Estándar", 2, Decimal("120000.00")),
            2: TipoHabitacion(2, "Familiar", 4, Decimal("200000.00")),
            3: TipoHabitacion(3, "Suite", 3, Decimal("280000.00")),
        }

    def buscar_por_id(self, id_tipo):
        self.reg.anotar("tipos.buscar_por_id")
        return self.datos.get(id_tipo)


class HabitacionesFalsas:
    def __init__(self, reg: Registro, libres: dict[int, list[Habitacion]]):
        self.reg = reg
        self.libres = libres

    def obtener_por_id(self, id_habitacion):
        self.reg.anotar("habitaciones.obtener_por_id")
        for lista in self.libres.values():
            for h in lista:
                if h.id_habitacion == id_habitacion:
                    return h
        return None

    def buscar_por_tipo(self, id_tipo):
        self.reg.anotar("habitaciones.buscar_por_tipo")
        return list(self.libres.get(id_tipo, []))

    def buscar_libres_por_tipo_y_rango(self, id_tipo, entrada, salida):
        self.reg.anotar("habitaciones.buscar_libres")
        return list(self.libres.get(id_tipo, []))


class HuespedesFalsos:
    def __init__(self, reg: Registro):
        self.reg = reg

    def obtener_por_id(self, id_huesped):
        self.reg.anotar("huespedes.obtener_por_id")
        return Huesped(1, "Ana Torres", "1020304050", None, None, None) if id_huesped == 1 else None


class ReservasFalsas:
    def __init__(self, reg: Registro, solapes: set[int] | None = None):
        self.reg = reg
        self.guardadas: dict[int, Reserva] = {}
        self.solapes = solapes or set()  # habitaciones que "otra solicitud" acaba de tomar

    def buscar_reservas_solapadas(self, id_habitacion, entrada, salida):
        self.reg.anotar("reservas.buscar_solapadas")
        return []

    def guardar(self, n: NuevaReserva) -> int:
        self.reg.anotar("reservas.guardar")
        if n.id_habitacion in self.solapes:
            self.solapes.discard(n.id_habitacion)
            raise SolapeReservaError("tomada por otra solicitud")
        nuevo = 4 + len(self.guardadas)
        self.guardadas[nuevo] = Reserva(
            nuevo, n.id_huesped, n.id_habitacion, n.fecha_entrada, n.fecha_salida,
            n.numero_personas, n.tarifa_noche, n.total, n.estado, datetime(2026, 11, 14, 10, 0),
        )
        return nuevo

    def buscar_por_id(self, id_reserva):
        self.reg.anotar("reservas.buscar_por_id")
        return self.guardadas.get(id_reserva)


class ProveedorFalso:
    """Misma forma que MongoProveedor; registra si se pidió leer o escribir."""

    def __init__(self, libres=None, solapes=None):
        self.reg = Registro()
        h = lambda i, n, t: Habitacion(i, n, t, "LIBRE")  # noqa: E731
        libres = libres if libres is not None else {
            2: [h(13, "201", 2), h(14, "202", 2)],
            3: [h(22, "302", 3), h(23, "303", 3), h(24, "304", 3)],
        }
        self.repos = Repositorios(
            tipos=TiposFalsos(self.reg),
            habitaciones=HabitacionesFalsas(self.reg, libres),
            huespedes=HuespedesFalsos(self.reg),
            reservas=ReservasFalsas(self.reg, solapes),
        )

    def leer(self, fn):
        self.reg.anotar("LEER")
        return fn(self.repos)

    def escribir(self, fn):
        self.reg.anotar("ESCRIBIR")
        return fn(self.repos)

    @property
    def llamadas(self):
        return self.reg.llamadas


def solicitud(**cambios) -> SolicitudReserva:
    base = dict(id_huesped=1, id_tipo=2, fecha_entrada=D(2026, 12, 20), fecha_salida=D(2026, 12, 23), numero_personas=3)
    base.update(cambios)
    return SolicitudReserva(**base)


def registrar(p: ProveedorFalso, **cambios):
    return RegistrarReservaService(p, hoy=lambda: HOY).registrar(solicitud(**cambios))


# ------------------------------------------------------------------ RF-04 Crear reserva
def test_rf04_registro_valido_asigna_menor_numero_y_calcula_total():
    p = ProveedorFalso()
    detalle = registrar(p)
    assert detalle.reserva.id_reserva == 4
    assert detalle.habitacion.numero == "201"  # la libre de menor número
    assert (detalle.noches, detalle.reserva.total, detalle.reserva.estado) == (3, Decimal("600000.00"), "CONFIRMADA")
    assert p.llamadas.count("reservas.guardar") == 1
    assert "ESCRIBIR" in p.llamadas


def test_rf04_sin_disponibilidad_no_invoca_guardar():
    p = ProveedorFalso(libres={2: []})
    with pytest.raises(SinDisponibilidadError):
        registrar(p)
    assert "reservas.guardar" not in p.llamadas


def test_rf04_capacidad_excedida_no_invoca_guardar():
    p = ProveedorFalso()
    with pytest.raises(CapacidadExcedidaError, match="como máximo 2 personas"):
        registrar(p, id_tipo=1, numero_personas=3)
    assert "reservas.guardar" not in p.llamadas


def test_rf04_huesped_inexistente_no_invoca_guardar():
    p = ProveedorFalso()
    with pytest.raises(NoEncontradoError, match="huésped"):
        registrar(p, id_huesped=99)
    assert "reservas.guardar" not in p.llamadas


@pytest.mark.parametrize(
    "entrada,salida",
    [(D(2026, 12, 23), D(2026, 12, 20)), (D(2026, 12, 20), D(2026, 12, 20)), (D(2026, 11, 13), D(2026, 11, 15))],
    ids=["salida-antes", "mismo-dia", "entrada-en-el-pasado"],
)
def test_rf04_fechas_invalidas_no_tocan_repositorios(entrada, salida):
    p = ProveedorFalso()
    with pytest.raises(FechasInvalidasError):
        registrar(p, fecha_entrada=entrada, fecha_salida=salida)
    assert p.llamadas == []  # se rechaza antes de leer o escribir


def test_rf04_si_otra_solicitud_toma_la_habitacion_reintenta_con_la_siguiente():
    p = ProveedorFalso(solapes={13})  # la 201 la toma otra solicitud al mismo tiempo
    detalle = registrar(p)
    assert detalle.habitacion.numero == "202"
    assert p.llamadas.count("ESCRIBIR") == 2
    assert p.llamadas.count("reservas.guardar") == 2


# ------------------------------------------------------------------ confirmación de RF-04
def test_consultar_reserva_existente_solo_lee():
    p = ProveedorFalso()
    creada = registrar(p).reserva.id_reserva
    p.reg.llamadas.clear()
    detalle = ConsultarReservaService(p).consultar(creada)
    assert detalle.reserva.id_reserva == creada and detalle.huesped.nombre == "Ana Torres"
    assert "LEER" in p.llamadas and "ESCRIBIR" not in p.llamadas
    assert "reservas.guardar" not in p.llamadas


def test_consultar_reserva_ausente():
    p = ProveedorFalso()
    with pytest.raises(NoEncontradoError, match="La reserva no existe"):
        ConsultarReservaService(p).consultar(999999)
    assert "ESCRIBIR" not in p.llamadas


@pytest.mark.parametrize("id_invalido", [0, -5])
def test_consultar_reserva_id_no_positivo(id_invalido):
    p = ProveedorFalso()
    with pytest.raises(EntradaInvalidaError):
        ConsultarReservaService(p).consultar(id_invalido)
    assert p.llamadas == []


# ------------------------------------------------------------------ RF-02 Consultar disponibilidad
def disponibilidad(p, **cambios):
    base = dict(id_tipo=3, fecha_entrada=D(2026, 12, 21), fecha_salida=D(2026, 12, 22), personas=2)
    base.update(cambios)
    return ConsultarDisponibilidadService(p, hoy=lambda: HOY).consultar(SolicitudDisponibilidad(**base))


def test_rf02_consulta_valida_solo_lee():
    p = ProveedorFalso()
    d = disponibilidad(p)
    assert [h.numero for h in d.habitaciones] == ["302", "303", "304"]
    assert (d.tipo.nombre, d.noches) == ("Suite", 1)
    assert "LEER" in p.llamadas and "ESCRIBIR" not in p.llamadas


def test_rf02_sin_habitaciones_devuelve_lista_vacia():
    p = ProveedorFalso(libres={3: []})
    assert disponibilidad(p).habitaciones == []


def test_rf02_tipo_inexistente():
    p = ProveedorFalso()
    with pytest.raises(NoEncontradoError, match="tipo"):
        disponibilidad(p, id_tipo=9)


def test_rf02_capacidad_excedida():
    p = ProveedorFalso()
    with pytest.raises(CapacidadExcedidaError):
        disponibilidad(p, personas=4)


def test_rf02_fechas_invalidas_no_tocan_repositorios():
    p = ProveedorFalso()
    with pytest.raises(FechasInvalidasError):
        disponibilidad(p, fecha_entrada=D(2026, 12, 22), fecha_salida=D(2026, 12, 21))
    assert p.llamadas == []
