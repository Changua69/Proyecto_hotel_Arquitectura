"""Prueba real por consola (Actividad 3, punto 4).

Uso:  python -m scripts.demo_persistencia

1. Consulta disponibilidad (RF-02) de Suites del 21 al 22 de diciembre: la 301 no aparece.
2. Guarda una reserva Familiar (RF-04) en una transacción y obtiene su id real.
3. Abre un CLIENTE NUEVO y recupera la reserva por id.
4. Busca un id inexistente.
5. Intenta una reserva solapada en la 301: la base la rechaza.
"""
from datetime import date
from decimal import Decimal

from app.persistence.db import en_transaccion, nueva_conexion, unidad_de_trabajo
from app.persistence.errors import SolapeReservaError
from app.persistence.models import NuevaReserva
from app.persistence.repositories import (
    MongoHabitacionRepository,
    MongoHuespedRepository,
    MongoReservaRepository,
    MongoTipoHabitacionRepository,
)

SUITE, FAMILIAR = 3, 2


def main() -> None:
    # 1. RF-02
    with unidad_de_trabajo() as uow:
        libres = MongoHabitacionRepository(uow).buscar_libres_por_tipo_y_rango(
            SUITE, date(2026, 12, 21), date(2026, 12, 22)
        )
        print("1) Suites libres 21-22 dic:", [h.numero for h in libres])

    # 2. RF-04: guardar
    def registrar(uow):
        tipo = MongoTipoHabitacionRepository(uow).buscar_por_id(FAMILIAR)
        huesped = MongoHuespedRepository(uow).obtener_por_id(1)
        hab = MongoHabitacionRepository(uow).buscar_libres_por_tipo_y_rango(
            FAMILIAR, date(2026, 12, 20), date(2026, 12, 23)
        )[0]
        noches = 3
        nueva = NuevaReserva(huesped.id_huesped, hab.id_habitacion, date(2026, 12, 20), date(2026, 12, 23),
                             3, tipo.tarifa_noche, tipo.tarifa_noche * noches)
        return MongoReservaRepository(uow).guardar(nueva), hab, nueva

    id_reserva, hab, nueva = en_transaccion(registrar)
    print(f"2) Reserva guardada id={id_reserva} habitación={hab.numero} total={nueva.total}")

    # 3. Cliente nuevo
    uow = nueva_conexion()
    try:
        r = MongoReservaRepository(uow).buscar_por_id(id_reserva)
        print(f"3) Recuperada desde un cliente nuevo: id={r.id_reserva} estado={r.estado} "
              f"{r.fecha_entrada}->{r.fecha_salida} total={r.total}")
        # 4. Id inexistente
        print("4) Reserva 999999:", MongoReservaRepository(uow).buscar_por_id(999999))
    finally:
        uow.cerrar()

    # 5. Integridad
    def solapada(uow):
        hab301 = [h for h in MongoHabitacionRepository(uow).buscar_por_tipo(SUITE) if h.numero == "301"][0]
        MongoReservaRepository(uow).guardar(NuevaReserva(2, hab301.id_habitacion, date(2026, 12, 21),
                                                         date(2026, 12, 22), 2, Decimal(280000), Decimal(280000)))

    try:
        en_transaccion(solapada)
        print("5) ERROR: se aceptó una reserva solapada")
    except SolapeReservaError as e:
        print("5) Solape rechazado por la BD:", e)


if __name__ == "__main__":
    main()
