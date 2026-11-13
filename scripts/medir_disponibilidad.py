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
from datetime import date, datetime, timedelta
from pathlib import Path

import pymongo

from app.persistence.db import base, cliente, unidad_de_trabajo
from app.persistence.repositories import MongoHabitacionRepository, a_dinero_bson, a_fecha_bson, noches_de
from scripts.reset_db import reset

UMBRAL_MS = 200
N_RESERVAS = 5000
EVID = Path(__file__).resolve().parent.parent / "evidencias"


def cargar_reservas() -> None:
    """Reservas de 2 noches consecutivas por habitación desde 2027-01-01 (no solapan)."""
    db = base()
    tarifas = {t["_id"]: t["tarifa_noche"].to_decimal() for t in db.tipos_habitacion.find()}
    habs = list(db.habitaciones.find().sort("_id", 1))
    siguiente = db.contadores.find_one({"_id": "reserva"})["valor"] + 1
    docs, inicio, i = [], date(2027, 1, 1), 0
    while len(docs) < N_RESERVAS:
        h = habs[i % len(habs)]
        tarifa = tarifas[h["id_tipo"]]
        entrada = inicio + timedelta(days=2 * (i // len(habs)))
        salida = entrada + timedelta(days=2)
        docs.append({
            "_id": siguiente + i, "id_huesped": 1, "id_habitacion": h["_id"],
            "fecha_entrada": a_fecha_bson(entrada), "fecha_salida": a_fecha_bson(salida),
            "noches": noches_de(entrada, salida), "numero_personas": 1,
            "tarifa_noche": a_dinero_bson(tarifa), "total": a_dinero_bson(tarifa * 2),
            "estado": "CONFIRMADA", "creada_en": datetime.now().replace(microsecond=0),
        })
        i += 1
    db.reservas.insert_many(docs)
    db.contadores.update_one({"_id": "reserva"}, {"$set": {"valor": siguiente + i - 1}})


def main() -> None:
    reset(verbose=False)
    cargar_reservas()
    tiempos = []
    with unidad_de_trabajo() as uow:
        total = uow.db.reservas.count_documents({}, session=uow.sesion)
        repo = MongoHabitacionRepository(uow)
        for k in range(20):
            entrada = date(2027, 3, 1) + timedelta(days=k)
            t0 = time.perf_counter()
            repo.buscar_libres_por_tipo_y_rango(1 + k % 3, entrada, entrada + timedelta(days=3))
            tiempos.append(round((time.perf_counter() - t0) * 1000, 3))
    version = cliente().server_info()["version"]
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
        "entorno": {"python": platform.python_version(), "pymongo": pymongo.__version__,
                    "mongodb": f"{version} (replica set de 1 nodo)", "so": platform.platform()},
    }
    EVID.mkdir(exist_ok=True)
    (EVID / "rnf01_tiempos.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
    print(json.dumps(resultado, indent=2))


if __name__ == "__main__":
    main()
