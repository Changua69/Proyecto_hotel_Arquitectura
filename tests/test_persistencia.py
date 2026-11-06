"""Pruebas de integración de la persistencia contra PostgreSQL real (semana 13).

Ejecutar:  pytest -v tests/
Cada prueba usa conexiones reales; ninguna simula la base de datos.
"""
import threading
from datetime import date
from decimal import Decimal

import pytest

from app.persistence.db import nueva_conexion, unidad_de_trabajo
from app.persistence.errors import DatosInvalidosError, ReferenciaInexistenteError, SolapeReservaError
from app.persistence.models import NuevaReserva
from app.persistence.repositories import (
    PgHabitacionRepository,
    PgHuespedRepository,
    PgReservaRepository,
    PgTipoHabitacionRepository,
)

ESTANDAR, FAMILIAR, SUITE = 1, 2, 3
D = date


def id_hab(numero: str) -> int:
    with unidad_de_trabajo() as conn:
        return conn.execute("SELECT id_habitacion FROM habitacion WHERE numero=%s", (numero,)).fetchone()[
            "id_habitacion"
        ]


def reserva(numero: str, entrada: date, salida: date, personas=2, huesped=1, tarifa=280000) -> NuevaReserva:
    noches = (salida - entrada).days
    return NuevaReserva(huesped, id_hab(numero), entrada, salida, personas, Decimal(tarifa), Decimal(tarifa * noches))


# ---------------------------------------------------------------- datos iniciales
def test_datos_iniciales_conteos_por_tipo():
    with unidad_de_trabajo() as conn:
        repo = PgHabitacionRepository(conn)
        assert [len(repo.buscar_por_tipo(t)) for t in (ESTANDAR, FAMILIAR, SUITE)] == [12, 8, 4]


def test_tipo_y_huesped_existentes_e_inexistentes():
    with unidad_de_trabajo() as conn:
        tipos, huespedes = PgTipoHabitacionRepository(conn), PgHuespedRepository(conn)
        familiar = tipos.buscar_por_id(FAMILIAR)
        assert (familiar.nombre, familiar.capacidad_max, familiar.tarifa_noche) == ("Familiar", 4, Decimal("200000.00"))
        assert tipos.buscar_por_id(99) is None
        assert huespedes.obtener_por_id(1).documento == "1020304050"
        assert huespedes.obtener_por_id(999) is None


# ---------------------------------------------------------------- RF-02 disponibilidad
def test_rf02_suite_301_no_aparece_si_esta_reservada():  # CA-02
    with unidad_de_trabajo() as conn:
        libres = PgHabitacionRepository(conn).buscar_libres_por_tipo_y_rango(SUITE, D(2026, 12, 21), D(2026, 12, 22))
    assert [h.numero for h in libres] == ["302", "303", "304"]  # 302 está CANCELADA: no bloquea


def test_rf02_rango_contiguo_no_cuenta_como_solape():  # CA-04
    with unidad_de_trabajo() as conn:
        libres = PgHabitacionRepository(conn).buscar_libres_por_tipo_y_rango(SUITE, D(2026, 12, 23), D(2026, 12, 25))
    assert "301" in [h.numero for h in libres]


def test_rf02_tipo_sin_reservas_devuelve_todas():
    with unidad_de_trabajo() as conn:
        libres = PgHabitacionRepository(conn).buscar_libres_por_tipo_y_rango(FAMILIAR, D(2026, 12, 20), D(2026, 12, 23))
    assert len(libres) == 8 and libres[0].numero == "201"


# ---------------------------------------------------------------- RF-04 escritura y lectura real
def test_rf04_guardar_y_recuperar_desde_conexion_nueva():
    nueva = reserva("201", D(2026, 12, 20), D(2026, 12, 23), personas=3, tarifa=200000)
    with unidad_de_trabajo() as conn:
        id_reserva = PgReservaRepository(conn).guardar(nueva)
    assert id_reserva == 4  # la secuencia continúa tras las 3 reservas de prueba

    # conexión completamente nueva, fuera de la transacción que escribió
    conn2 = nueva_conexion()
    try:
        r = PgReservaRepository(conn2).buscar_por_id(id_reserva)
    finally:
        conn2.close()
    assert r is not None
    assert (r.estado, r.numero_personas, r.total) == ("CONFIRMADA", 3, Decimal("600000.00"))  # CA-01
    assert (r.fecha_entrada, r.fecha_salida) == (D(2026, 12, 20), D(2026, 12, 23))


def test_rf04_id_inexistente_devuelve_none():
    with unidad_de_trabajo() as conn:
        assert PgReservaRepository(conn).buscar_por_id(999999) is None


def test_rf04_buscar_reservas_solapadas():
    with unidad_de_trabajo() as conn:
        repo = PgReservaRepository(conn)
        assert [r.id_reserva for r in repo.buscar_reservas_solapadas(id_hab("301"), D(2026, 12, 22), D(2026, 12, 24))] == [1]
        assert repo.buscar_reservas_solapadas(id_hab("301"), D(2026, 12, 23), D(2026, 12, 24)) == []
        assert repo.buscar_reservas_solapadas(id_hab("302"), D(2026, 12, 21), D(2026, 12, 22)) == []  # cancelada


# ---------------------------------------------------------------- restricciones de integridad
def test_integridad_exclusion_rechaza_solape():  # RN-01 reforzada en BD
    with pytest.raises(SolapeReservaError):
        with unidad_de_trabajo() as conn:
            PgReservaRepository(conn).guardar(reserva("301", D(2026, 12, 21), D(2026, 12, 22)))


def test_integridad_check_fechas():  # RN-03 reforzada en BD
    with pytest.raises(DatosInvalidosError):
        with unidad_de_trabajo() as conn:
            PgReservaRepository(conn).guardar(
                NuevaReserva(1, id_hab("202"), D(2026, 12, 23), D(2026, 12, 20), 2, Decimal(200000), Decimal(200000))
            )


def test_integridad_fk_huesped_inexistente():  # RN-05 reforzada en BD
    with pytest.raises(ReferenciaInexistenteError):
        with unidad_de_trabajo() as conn:
            PgReservaRepository(conn).guardar(reserva("202", D(2026, 12, 20), D(2026, 12, 21), huesped=999))


# ---------------------------------------------------------------- RNF-03 atomicidad
def test_rnf03_error_en_transaccion_no_deja_datos_parciales():
    with pytest.raises(RuntimeError):
        with unidad_de_trabajo() as conn:
            PgReservaRepository(conn).guardar(reserva("203", D(2026, 12, 20), D(2026, 12, 21)))
            raise RuntimeError("falla simulada después de guardar")
    with unidad_de_trabajo() as conn:
        assert PgReservaRepository(conn).buscar_reservas_solapadas(id_hab("203"), D(2026, 12, 20), D(2026, 12, 21)) == []


def test_rnf03_savepoint_permite_reintentar_con_otra_habitacion():
    """Algoritmo de asignación (sección 10): si la BD rechaza una habitación, la misma
    transacción reintenta con otra libre."""
    with unidad_de_trabajo() as conn:
        repo = PgReservaRepository(conn)
        with pytest.raises(SolapeReservaError):
            repo.guardar(reserva("301", D(2026, 12, 21), D(2026, 12, 22)))
        id_ok = repo.guardar(reserva("303", D(2026, 12, 21), D(2026, 12, 22)))
    with unidad_de_trabajo() as conn:
        assert PgReservaRepository(conn).buscar_por_id(id_ok).id_habitacion == id_hab("303")


# ---------------------------------------------------------------- RNF-08 concurrencia (CA-07)
def test_rnf08_diez_solicitudes_simultaneas_una_sola_reserva():
    hab = id_hab("304")
    nueva = NuevaReserva(1, hab, D(2026, 12, 26), D(2026, 12, 28), 2, Decimal(280000), Decimal(560000))
    barrera, resultados = threading.Barrier(10), []

    def intentar():
        barrera.wait()
        try:
            with unidad_de_trabajo() as conn:
                PgReservaRepository(conn).guardar(nueva)
            resultados.append("ok")
        except SolapeReservaError:
            resultados.append("409")

    hilos = [threading.Thread(target=intentar) for _ in range(10)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(resultados) == ["409"] * 9 + ["ok"]
    with unidad_de_trabajo() as conn:
        assert len(PgReservaRepository(conn).buscar_reservas_solapadas(hab, D(2026, 12, 26), D(2026, 12, 28))) == 1
