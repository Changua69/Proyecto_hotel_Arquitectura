"""Servicios de aplicación de RF-02 y RF-04 (semana 14).

Responsabilidades:
- El servicio coordina el caso de uso y aplica las reglas RN-01 a RN-05.
- Los repositorios solo consultan y guardan (semana 13).
- La API solo traduce HTTP <-> servicio; no contiene reglas.

Los servicios reciben un `ProveedorRepositorios`, así que se prueban con uno en memoria
sin abrir conexiones (RNF-06) y en producción con `MongoProveedor`.
"""
from dataclasses import dataclass
from datetime import date
from typing import Callable

from app.persistence.errors import (
    DatosInvalidosError as DatosRechazadosPorBD,
    ReferenciaInexistenteError,
    SolapeReservaError,
)
from app.persistence.models import Habitacion, Huesped, NuevaReserva, Reserva, TipoHabitacion
from app.persistence.proveedor import ProveedorRepositorios, Repositorios
from app.services.errores import (
    CapacidadExcedidaError,
    EntradaInvalidaError,
    FechasInvalidasError,
    NoEncontradoError,
    SinDisponibilidadError,
)

Reloj = Callable[[], date]

MSG_FECHAS = "La fecha de salida debe ser posterior a la de entrada."
MSG_PASADO = "La fecha de entrada no puede ser anterior a hoy."
MSG_TIPO = "El tipo de habitación no existe."
MSG_HUESPED = "El huésped no existe."
MSG_RESERVA = "La reserva no existe."
MSG_SIN_DISP = "No hay habitaciones disponibles para esas fechas."


# ------------------------------------------------------------------ objetos de entrada y salida
@dataclass(frozen=True)
class SolicitudDisponibilidad:
    id_tipo: int
    fecha_entrada: date
    fecha_salida: date
    personas: int


@dataclass(frozen=True)
class Disponibilidad:
    tipo: TipoHabitacion
    fecha_entrada: date
    fecha_salida: date
    personas: int
    habitaciones: list[Habitacion]

    @property
    def noches(self) -> int:
        return (self.fecha_salida - self.fecha_entrada).days


@dataclass(frozen=True)
class SolicitudReserva:
    id_huesped: int
    id_tipo: int
    fecha_entrada: date
    fecha_salida: date
    numero_personas: int


@dataclass(frozen=True)
class ReservaDetalle:
    """Reserva persistida con los datos que necesita la confirmación (RF-04)."""

    reserva: Reserva
    huesped: Huesped
    habitacion: Habitacion
    tipo: TipoHabitacion

    @property
    def noches(self) -> int:
        return (self.reserva.fecha_salida - self.reserva.fecha_entrada).days


# ------------------------------------------------------------------ reglas compartidas
def validar_fechas(entrada: date, salida: date, hoy: date) -> None:
    """RN-03 y RN-04. Se valida antes de tocar los repositorios."""
    if salida <= entrada:
        raise FechasInvalidasError(MSG_FECHAS)
    if entrada < hoy:
        raise FechasInvalidasError(MSG_PASADO)


def tipo_con_capacidad(r: Repositorios, id_tipo: int, personas: int) -> TipoHabitacion:
    """RN-05 (el tipo existe) y RN-02 (capacidad)."""
    tipo = r.tipos.buscar_por_id(id_tipo)
    if tipo is None:
        raise NoEncontradoError(MSG_TIPO)
    if personas > tipo.capacidad_max:
        raise CapacidadExcedidaError(
            f"El tipo {tipo.nombre} admite como máximo {tipo.capacidad_max} personas."
        )
    return tipo


# ------------------------------------------------------------------ RF-02
class ConsultarDisponibilidadService:
    """RF-02. Consultar disponibilidad: habitaciones libres del tipo en el rango."""

    def __init__(self, proveedor: ProveedorRepositorios, hoy: Reloj = date.today):
        self._proveedor = proveedor
        self._hoy = hoy

    def consultar(self, sol: SolicitudDisponibilidad) -> Disponibilidad:
        validar_fechas(sol.fecha_entrada, sol.fecha_salida, self._hoy())

        def caso(r: Repositorios) -> Disponibilidad:
            tipo = tipo_con_capacidad(r, sol.id_tipo, sol.personas)
            libres = r.habitaciones.buscar_libres_por_tipo_y_rango(
                sol.id_tipo, sol.fecha_entrada, sol.fecha_salida
            )
            return Disponibilidad(tipo, sol.fecha_entrada, sol.fecha_salida, sol.personas, libres)

        return self._proveedor.leer(caso)


# ------------------------------------------------------------------ RF-04
class RegistrarReservaService:
    """RF-04. Crear reserva (incluye los rechazos de RF-05).

    Algoritmo (documento del segundo corte, sección 10):
    1. Validar fechas (RN-03, RN-04).
    2. En una transacción: huésped existe (RN-05), tipo existe (RN-05), capacidad (RN-02),
       tomar la habitación libre de MENOR número (RN-01) y guardar con estado CONFIRMADA.
    3. Si la base rechaza esa habitación porque otra solicitud la tomó al mismo tiempo
       (índice único de noches), repetir el paso 2 en una transacción NUEVA con otra habitación.
    4. Si no queda ninguna, SIN_DISPONIBILIDAD (409).
    La respuesta se construye solo después de confirmar la transacción.
    """

    def __init__(self, proveedor: ProveedorRepositorios, hoy: Reloj = date.today, max_intentos: int = 10):
        self._proveedor = proveedor
        self._hoy = hoy
        self._max_intentos = max_intentos

    def registrar(self, sol: SolicitudReserva) -> ReservaDetalle:
        validar_fechas(sol.fecha_entrada, sol.fecha_salida, self._hoy())
        descartadas: set[int] = set()

        for _ in range(self._max_intentos):
            elegida: list[int] = []

            def caso(r: Repositorios) -> ReservaDetalle:
                elegida.clear()
                huesped = r.huespedes.obtener_por_id(sol.id_huesped)
                if huesped is None:
                    raise NoEncontradoError(MSG_HUESPED)
                tipo = tipo_con_capacidad(r, sol.id_tipo, sol.numero_personas)
                libres = [
                    h
                    for h in r.habitaciones.buscar_libres_por_tipo_y_rango(
                        sol.id_tipo, sol.fecha_entrada, sol.fecha_salida
                    )
                    if h.id_habitacion not in descartadas
                ]
                if not libres:
                    raise SinDisponibilidadError(MSG_SIN_DISP)
                habitacion = libres[0]  # el repositorio las entrega ordenadas por número
                elegida.append(habitacion.id_habitacion)
                noches = (sol.fecha_salida - sol.fecha_entrada).days
                id_reserva = r.reservas.guardar(
                    NuevaReserva(
                        id_huesped=sol.id_huesped,
                        id_habitacion=habitacion.id_habitacion,
                        fecha_entrada=sol.fecha_entrada,
                        fecha_salida=sol.fecha_salida,
                        numero_personas=sol.numero_personas,
                        tarifa_noche=tipo.tarifa_noche,
                        total=tipo.tarifa_noche * noches,
                        estado="CONFIRMADA",
                    )
                )
                reserva = r.reservas.buscar_por_id(id_reserva)
                return ReservaDetalle(reserva, huesped, habitacion, tipo)

            try:
                return self._proveedor.escribir(caso)
            except SolapeReservaError:
                descartadas.update(elegida)  # otra solicitud la tomó: probar la siguiente
            except ReferenciaInexistenteError as e:
                raise NoEncontradoError(MSG_HUESPED) from e
            except DatosRechazadosPorBD as e:
                raise FechasInvalidasError(MSG_FECHAS) from e

        raise SinDisponibilidadError(MSG_SIN_DISP)


# ------------------------------------------------------------------ confirmación de RF-04
class ConsultarReservaService:
    """Confirmación de RF-04 (RF-06 del segundo corte): recuperar una reserva por su id.
    Permite comprobar si una reserva quedó guardada antes de repetir una escritura."""

    def __init__(self, proveedor: ProveedorRepositorios):
        self._proveedor = proveedor

    def consultar(self, id_reserva: int) -> ReservaDetalle:
        if not isinstance(id_reserva, int) or isinstance(id_reserva, bool) or id_reserva <= 0:
            raise EntradaInvalidaError("El identificador de la reserva debe ser un entero positivo.")

        def caso(r: Repositorios) -> ReservaDetalle:
            reserva = r.reservas.buscar_por_id(id_reserva)
            if reserva is None:
                raise NoEncontradoError(MSG_RESERVA)
            habitacion = r.habitaciones.obtener_por_id(reserva.id_habitacion)
            tipo = r.tipos.buscar_por_id(habitacion.id_tipo)
            huesped = r.huespedes.obtener_por_id(reserva.id_huesped)
            return ReservaDetalle(reserva, huesped, habitacion, tipo)

        return self._proveedor.leer(caso)
