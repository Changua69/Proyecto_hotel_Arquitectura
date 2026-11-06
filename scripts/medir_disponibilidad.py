"""Medición de RNF-01 (parte de persistencia, semana 1).

Uso:  python -m scripts.medir_disponibilidad

Carga 5 000 reservas sintéticas (no solapadas) sobre la base de prueba, ejecuta 20
consultas consecutivas de disponibilidad y guarda los tiempos en evidencias/.
Umbral semana 1 (solo repositorio): cada consulta <= 200 ms.
Al final recrea el estado inicial para no contaminar las demás pruebas.
"""
import json
import platform
import statistics
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg

from app.persistence.db import unidad_de_trabajo
from app.persistence.repositories import PgHabitacionRepository
from scripts.reset_db import reset

UMBRAL_MS = 200
N_RESERVAS = 5000
EVID = Path(__file__).resolve().parent.parent / "evidencias"


def cargar_reservas() -> None:
    """Reservas de 2 noches consecutivas por habitación desde 2027-01-01 (no solapan)."""
    with unidad_de_trabajo() as conn:
        habs = conn.execute("""SELECT h.id_habitacion, t.tarifa_noche FROM habitacion h
                               JOIN tipo_habitacion t USING (id_tipo) ORDER BY h.id_habitacion""").fetchall()
        filas, inicio, i = [], date(2027, 1, 1), 0
        while len(filas) < N_RESERVAS:
            h = habs[i % len(habs)]
            entrada = inicio + timedelta(days=2 * (i // len(habs)))
            filas.append((1, h["id_habitacion"], entrada, entrada + timedelta(days=2), 1,
                          h["tarifa_noche"], h["tarifa_noche"] * 2))
            i += 1
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO reserva (id_huesped, id_habitacion, fecha_entrada, fecha_salida,
                               numero_personas, tarifa_noche, total) VALUES (%s,%s,%s,%s,%s,%s,%s)""", filas)
        conn.execute("ANALYZE reserva")


def main() -> None:
    reset(verbose=False)
    cargar_reservas()
    tiempos = []
    with unidad_de_trabajo() as conn:
        total = conn.execute("SELECT count(*) AS n FROM reserva").fetchone()["n"]
        repo = PgHabitacionRepository(conn)
        for k in range(20):
            entrada = date(2027, 3, 1) + timedelta(days=k)
            t0 = time.perf_counter()
            libres = repo.buscar_libres_por_tipo_y_rango(1 + k % 3, entrada, entrada + timedelta(days=3))
            tiempos.append(round((time.perf_counter() - t0) * 1000, 3))
        pg_version = conn.execute("SHOW server_version").fetchone()["server_version"]
    reset(verbose=False)

    resultado = {
        "rnf": "RNF-01 (persistencia)",
        "reservas_en_base": total,
        "consultas": 20,
        "tiempos_ms": tiempos,
        "max_ms": max(tiempos),
        "promedio_ms": round(statistics.mean(tiempos), 3),
        "umbral_ms": UMBRAL_MS,
        "cumple": max(tiempos) <= UMBRAL_MS,
        "entorno": {"python": platform.python_version(), "psycopg": psycopg.__version__,
                    "postgresql": pg_version, "so": platform.platform()},
    }
    EVID.mkdir(exist_ok=True)
    (EVID / "rnf01_tiempos.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
    print(json.dumps(resultado, indent=2))


if __name__ == "__main__":
    main()
