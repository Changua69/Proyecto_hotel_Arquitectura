"""Prueba real por consola (Actividad 3, punto 4).

Uso:  python -m scripts.demo_persistencia

1. Consulta disponibilidad (RF-02) de Suites del 21 al 22 de diciembre: la 301 no aparece.
2. Guarda una reserva Familiar (RF-04) en una transacción y obtiene su id real.
3. Abre una CONEXIÓN NUEVA y recupera la reserva por id.
4. Busca un id inexistente.
5. Intenta una reserva solapada en la 301: la base la rechaza.
"""
from datetime import date
from decimal import Decimal

from app.persistence.db import unidad_de_trabajo
from app.persistence.errors import SolapeReservaError
from app.persistence.models import NuevaReserva
from app.persistence.repositories import (
    PgHabitacionRepository,
    PgHuespedRepository,
    PgReservaRepository,
    PgTipoHabitacionRepository,
)

SUITE, FAMILIAR = 3, 2


def main() -> None:
    # 1. RF-02
    with unidad_de_trabajo() as conn:
        libres = PgHabitacionRepository(conn).buscar_libres_por_tipo_y_rango(
            SUITE, date(2026, 12, 21), date(2026, 12, 22)
        )
        print("1) Suites libres 21-22 dic:", [h.numero for h in libres])

    # 2. RF-04: guardar
    with unidad_de_trabajo() as conn:
        tipo = PgTipoHabitacionRepository(conn).buscar_por_id(FAMILIAR)
        huesped = PgHuespedRepository(conn).obtener_por_id(1)
        hab = PgHabitacionRepository(conn).buscar_libres_por_tipo_y_rango(
            FAMILIAR, date(2026, 12, 20), date(2026, 12, 23)
        )[0]
        noches = 3
        nueva = NuevaReserva(huesped.id_huesped, hab.id_habitacion, date(2026, 12, 20), date(2026, 12, 23),
                             3, tipo.tarifa_noche, tipo.tarifa_noche * noches)
        id_reserva = PgReservaRepository(conn).guardar(nueva)
        print(f"2) Reserva guardada id={id_reserva} habitación={hab.numero} total={nueva.total}")

    # 3. Conexión nueva
    with unidad_de_trabajo() as conn:
        r = PgReservaRepository(conn).buscar_por_id(id_reserva)
        print(f"3) Recuperada desde conexión nueva: id={r.id_reserva} estado={r.estado} "
              f"{r.fecha_entrada}->{r.fecha_salida} total={r.total}")

    # 4. Id inexistente
    with unidad_de_trabajo() as conn:
        print("4) Reserva 999999:", PgReservaRepository(conn).buscar_por_id(999999))

    # 5. Integridad
    try:
        with unidad_de_trabajo() as conn:
            hab301 = [h for h in PgHabitacionRepository(conn).buscar_por_tipo(SUITE) if h.numero == "301"][0]
            PgReservaRepository(conn).guardar(NuevaReserva(2, hab301.id_habitacion, date(2026, 12, 21),
                                                           date(2026, 12, 22), 2, Decimal(280000), Decimal(280000)))
        print("5) ERROR: se aceptó una reserva solapada")
    except SolapeReservaError as e:
        print("5) Solape rechazado por la BD:", e)


if __name__ == "__main__":
    main()
