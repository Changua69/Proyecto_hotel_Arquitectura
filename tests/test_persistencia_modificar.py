"""Persistencia de MODIFICAR RESERVA contra MongoDB real.

Ejecutar:  python -m pytest tests/test_persistencia_modificar.py -v

Qué se demuestra (cada prueba usa conexiones reales a un replica set, nada simulado):
  P1  Lo modificado queda guardado: se relee desde un cliente NUEVO (otra conexión, sin sesión).
  P2  El arreglo `noches` y el total quedan coherentes con las nuevas fechas (índice anti-solape).
  P3  Acortar una reserva libera las noches: otra reserva puede tomarlas.
  P4  Si hay cambio de habitación, el cambio persiste y la habitación anterior queda libre.
  P5  Atomicidad: si algo falla después de modificar, la transacción se revierte (0 cambios parciales).
  P6  Un rechazo (409, 403, reserva cancelada) no toca ningún documento.
  P7  "Reinicio del backend": se cierra el cliente compartido, se reconecta y el dato sigue ahí.
  P8  10 modificaciones simultáneas de LA MISMA reserva: el documento final es coherente.
  P9  2 reservas compiten por la última habitación libre: 1 gana, 1 recibe 409, sin solapes.

Usan un reloj fijo (HOY) en vez de la fecha real, para que no dependan del día en que se ejecuten.
Estado inicial (db/datos_prueba.py): R1 = Ana, Suite 301 (id 21), 20-23 dic 2026, $280.000/noche.
"""
import threading
from datetime import date, datetime
from decimal import Decimal

import pytest

import app.persistence.db as db_mod
from app.persistence.db import base, en_transaccion, nueva_conexion
from app.persistence.proveedor import MongoProveedor
from app.persistence.repositories import MongoReservaRepository, noches_de
from app.services.errores import (
    ReservaNoModificableError,
    SinDisponibilidadError,
    SinPermisoError,
)
from app.services.reservas import (
    CambioReserva,
    ModificarReservaService,
    RegistrarReservaService,
    SolicitudReserva,
)

D = date
HOY = D(2026, 11, 1)  # reloj fijo
SUITE, ID_301, ID_303, ID_304 = 3, 21, 23, 24


# ------------------------------------------------------------------ ayudas
def modificar(id_reserva, entrada, salida, personas=2, solo_de=None):
    return ModificarReservaService(MongoProveedor(), hoy=lambda: HOY).modificar(
        id_reserva, CambioReserva(entrada, salida, personas), solo_de)


def crear(entrada, salida, tipo=SUITE, huesped=2, personas=1):
    return RegistrarReservaService(MongoProveedor(), hoy=lambda: HOY).registrar(
        SolicitudReserva(huesped, tipo, entrada, salida, personas))


def leer_desde_cliente_nuevo(id_reserva: int) -> dict:
    """Documento crudo leído con una conexión completamente nueva (nada en memoria del backend)."""
    uow = nueva_conexion()
    try:
        return uow.db.reservas.find_one({"_id": id_reserva})
    finally:
        uow.cerrar()


def ocupantes_de_noche(id_habitacion: int, noche: date) -> int:
    return base().reservas.count_documents({
        "id_habitacion": id_habitacion,
        "estado": {"$in": ["CONFIRMADA", "EN_CURSO"]},
        "noches": datetime(noche.year, noche.month, noche.day),
    })


# ------------------------------------------------------------------ P1 / P2
def test_p1_la_modificacion_queda_guardada_en_otra_conexion():
    modificar(1, D(2026, 12, 20), D(2026, 12, 25), personas=3)

    d = leer_desde_cliente_nuevo(1)
    assert d["fecha_entrada"] == datetime(2026, 12, 20)
    assert d["fecha_salida"] == datetime(2026, 12, 25)
    assert d["numero_personas"] == 3
    assert d["total"].to_decimal() == Decimal("1400000.00")   # 5 noches x 280.000
    assert d["estado"] == "CONFIRMADA"
    assert d["id_habitacion"] == ID_301                      # conserva su habitación


def test_p2_noches_y_tarifa_coherentes_con_las_nuevas_fechas():
    modificar(1, D(2026, 12, 18), D(2026, 12, 22))

    d = leer_desde_cliente_nuevo(1)
    assert d["noches"] == noches_de(D(2026, 12, 18), D(2026, 12, 22))   # 18, 19, 20, 21
    assert len(d["noches"]) == 4
    assert d["tarifa_noche"].to_decimal() == Decimal("280000.00")       # la tarifa acordada no cambia
    assert d["total"].to_decimal() == Decimal("1120000.00")


# ------------------------------------------------------------------ P3 / P4
def test_p3_acortar_libera_las_noches_para_otra_reserva():
    modificar(1, D(2026, 12, 20), D(2026, 12, 21))           # ahora solo la noche del 20
    assert ocupantes_de_noche(ID_301, D(2026, 12, 21)) == 0
    assert ocupantes_de_noche(ID_301, D(2026, 12, 22)) == 0

    nueva = crear(D(2026, 12, 21), D(2026, 12, 23))
    assert nueva.habitacion.numero == "301"                  # la menor libre: la que acaba de liberarse


def test_p4_cambio_de_habitacion_persiste_y_libera_la_anterior():
    crear(D(2026, 12, 23), D(2026, 12, 26))                  # toma la 301
    crear(D(2026, 12, 23), D(2026, 12, 26))                  # toma la 302
    detalle = modificar(1, D(2026, 12, 21), D(2026, 12, 25))
    assert detalle.habitacion.numero == "303"

    d = leer_desde_cliente_nuevo(1)
    assert d["id_habitacion"] == ID_303
    assert ocupantes_de_noche(ID_301, D(2026, 12, 21)) == 0  # ya no ocupa la 301 esa noche
    assert ocupantes_de_noche(ID_303, D(2026, 12, 21)) == 1


# ------------------------------------------------------------------ P5 / P6
def test_p5_falla_despues_de_modificar_revierte_todo():
    antes = leer_desde_cliente_nuevo(1)

    def caso(uow):
        MongoReservaRepository(uow).modificar(1, ID_301, D(2026, 12, 20), D(2026, 12, 30), 3, Decimal(2_800_000))
        raise RuntimeError("falla simulada después de modificar")

    with pytest.raises(RuntimeError):
        en_transaccion(caso)

    assert leer_desde_cliente_nuevo(1) == antes              # ni fechas, ni noches, ni total cambiaron


def test_p6_los_rechazos_no_tocan_ningun_documento():
    instantanea = lambda: [leer_desde_cliente_nuevo(i) for i in (1, 2, 3)]  # noqa: E731

    # 6a. sin disponibilidad: 301-304 ocupadas desde el 24 y se pide alargar la R1 hasta el 26
    for _ in range(4):
        crear(D(2026, 12, 24), D(2026, 12, 26))
    antes = instantanea()
    with pytest.raises(SinDisponibilidadError):
        modificar(1, D(2026, 12, 20), D(2026, 12, 26))
    assert instantanea() == antes

    # 6b. un huésped no puede modificar la reserva de otro (R3 es de Laura = huésped 3)
    with pytest.raises(SinPermisoError):
        modificar(3, D(2026, 12, 10), D(2026, 12, 14), personas=1, solo_de=1)
    assert instantanea() == antes

    # 6c. una reserva CANCELADA (R2) no se modifica
    with pytest.raises(ReservaNoModificableError):
        modificar(2, D(2026, 12, 20), D(2026, 12, 24))
    assert instantanea() == antes


# ------------------------------------------------------------------ P7
def test_p7_reinicio_del_backend_no_pierde_la_modificacion():
    modificar(1, D(2026, 12, 20), D(2026, 12, 24), personas=2)

    # Simula apagar y volver a encender el backend: se descarta el cliente compartido (y su pool).
    db_mod._cliente.close()
    db_mod._cliente = None

    d = base().reservas.find_one({"_id": 1})                 # base() abre un cliente nuevo
    assert d["fecha_salida"] == datetime(2026, 12, 24)
    assert len(d["noches"]) == 4


# ------------------------------------------------------------------ P8 / P9
def test_p8_diez_modificaciones_simultaneas_de_la_misma_reserva_dejan_un_documento_coherente():
    barrera, resultados, candado = threading.Barrier(10), [], threading.Lock()

    def intentar(k: int):
        barrera.wait()
        try:
            modificar(1, D(2026, 12, 20), D(2026, 12, 21 + k), personas=2)   # 1 a 10 noches
            r = "ok"
        except Exception as e:  # noqa: BLE001
            r = f"error:{type(e).__name__}"
        with candado:
            resultados.append(r)

    hilos = [threading.Thread(target=intentar, args=(k,)) for k in range(10)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert resultados == ["ok"] * 10, resultados             # todas terminan; los conflictos se reintentan
    d = leer_desde_cliente_nuevo(1)
    entrada, salida = d["fecha_entrada"].date(), d["fecha_salida"].date()
    # Gana la última escritura, pero el documento nunca queda "mezclado":
    assert d["noches"] == noches_de(entrada, salida)
    assert d["total"].to_decimal() == Decimal(280000) * (salida - entrada).days


def test_p9_dos_reservas_compiten_por_la_ultima_habitacion_libre():
    # 28-30 dic: 301, 302 y 303 ocupadas; solo queda la 304.
    for _ in range(3):
        crear(D(2026, 12, 28), D(2026, 12, 30))
    r_b = crear(D(2026, 12, 24), D(2026, 12, 26)).reserva.id_reserva   # otra reserva Suite (en la 301)
    antes = {1: leer_desde_cliente_nuevo(1), r_b: leer_desde_cliente_nuevo(r_b)}

    barrera, resultados, candado = threading.Barrier(2), {}, threading.Lock()

    def intentar(id_reserva: int):
        barrera.wait()
        try:
            modificar(id_reserva, D(2026, 12, 28), D(2026, 12, 30))
            r = "ok"
        except SinDisponibilidadError:
            r = "409"
        with candado:
            resultados[id_reserva] = r

    hilos = [threading.Thread(target=intentar, args=(i,)) for i in (1, r_b)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(resultados.values()) == ["409", "ok"], resultados
    assert ocupantes_de_noche(ID_304, D(2026, 12, 28)) == 1  # una sola dueña de la 304
    perdedora = next(i for i, r in resultados.items() if r == "409")
    assert leer_desde_cliente_nuevo(perdedora) == antes[perdedora]   # la que perdió quedó exactamente igual
