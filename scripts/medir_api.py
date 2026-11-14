"""Medición de RNF-01 por HTTP (semana 14).

RNF-01 — Eficiencia de desempeño / comportamiento temporal, asociado a RF-02 y RF-04.
Meta acordada en la semana 13 para la API: p95 <= 2 s con 10 usuarios concurrentes y
>= 5 000 reservas en la base.

Uso:  python -m scripts.medir_api

Qué hace:
1. Recrea la base y carga 5 000 reservas sintéticas (las mismas de medir_disponibilidad).
2. Levanta la API real (uvicorn) en 127.0.0.1:8001, dentro de este proceso.
3. 10 usuarios (hilos) hacen al mismo tiempo 20 consultas GET /api/disponibilidad cada uno
   (200 solicitudes). Se mide la respuesta HTTP COMPLETA desde el cliente (enviar, esperar y
   leer el cuerpo), por la interfaz de red local.
4. Además, como referencia, 20 consultas consecutivas de un solo cliente.
5. Guarda tiempos, códigos y entorno en evidencias/semana14/rnf01_api.json y restaura la base.
"""
import json
import math
import platform
import statistics
import threading
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
import pymongo
import uvicorn

from app.persistence.db import base
from scripts.medir_disponibilidad import cargar_reservas
from scripts.reset_db import reset

HOST, PUERTO = "127.0.0.1", 8001
URL = f"http://{HOST}:{PUERTO}"
USUARIOS, POR_USUARIO = 10, 20
UMBRAL_P95_MS = 2000
EVID = Path(__file__).resolve().parent.parent / "evidencias" / "semana14"


def p95(valores: list[float]) -> float:
    """Percentil 95 por rango más cercano (sin interpolar)."""
    ordenados = sorted(valores)
    return ordenados[math.ceil(0.95 * len(ordenados)) - 1]


def parametros(k: int) -> dict:
    entrada = date(2027, 3, 1) + timedelta(days=k % 60)
    return {
        "id_tipo": 1 + k % 3,
        "fecha_entrada": entrada.isoformat(),
        "fecha_salida": (entrada + timedelta(days=3)).isoformat(),
        "personas": 1,
    }


def levantar_api() -> uvicorn.Server:
    from app.api.app import app

    servidor = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PUERTO, log_level="warning"))
    threading.Thread(target=servidor.run, daemon=True).start()
    for _ in range(100):
        if servidor.started:
            return servidor
        time.sleep(0.05)
    raise RuntimeError("La API no arrancó")


def medir(cliente: httpx.Client, k: int) -> tuple[float, int]:
    t0 = time.perf_counter()
    r = cliente.get(f"{URL}/api/disponibilidad", params=parametros(k))
    r.read()
    return round((time.perf_counter() - t0) * 1000, 2), r.status_code


def main() -> None:
    reset(verbose=False)
    cargar_reservas()
    total_reservas = base().reservas.count_documents({})
    servidor = levantar_api()

    with httpx.Client() as c:  # calentamiento: 1 solicitud excluida de la medición
        c.get(f"{URL}/api/disponibilidad", params=parametros(0))

    # --- escenario de la meta: 10 usuarios concurrentes
    barrera, resultados, candado = threading.Barrier(USUARIOS), [], threading.Lock()

    def usuario(u: int) -> None:
        with httpx.Client() as c:
            barrera.wait()
            for i in range(POR_USUARIO):
                ms, codigo = medir(c, u * POR_USUARIO + i)
                with candado:
                    resultados.append({"usuario": u + 1, "ms": ms, "http": codigo})

    t0 = time.perf_counter()
    hilos = [threading.Thread(target=usuario, args=(u,)) for u in range(USUARIOS)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    duracion = time.perf_counter() - t0

    tiempos = [r["ms"] for r in resultados]
    codigos = sorted({r["http"] for r in resultados})

    # --- referencia: 20 consultas consecutivas, un cliente
    with httpx.Client() as c:
        secuenciales = [medir(c, k) for k in range(20)]

    servidor.should_exit = True
    time.sleep(0.3)
    reset(verbose=False)

    resultado = {
        "rnf": "RNF-01 (API, semana 14)",
        "escenario": f"{USUARIOS} usuarios concurrentes x {POR_USUARIO} consultas GET /api/disponibilidad",
        "medida": "respuesta HTTP completa desde el cliente, en ms",
        "reservas_en_base": total_reservas,
        "solicitudes": len(tiempos),
        "codigos_http": codigos,
        "todas_200": codigos == [200],
        "p95_ms": p95(tiempos),
        "max_ms": max(tiempos),
        "promedio_ms": round(statistics.mean(tiempos), 2),
        "solicitudes_por_segundo": round(len(tiempos) / duracion, 1),
        "umbral_p95_ms": UMBRAL_P95_MS,
        "cumple": p95(tiempos) <= UMBRAL_P95_MS and codigos == [200],
        "referencia_20_consecutivas": {
            "tiempos_ms": [ms for ms, _ in secuenciales],
            "codigos_http": sorted({c for _, c in secuenciales}),
            "max_ms": max(ms for ms, _ in secuenciales),
        },
        "condiciones": "API y MongoDB en el mismo equipo (localhost); 1 solicitud de calentamiento "
        "excluida; sin caché en la API; la caché propia de MongoDB queda activa tras el calentamiento.",
        "entorno": {
            "python": platform.python_version(),
            "pymongo": pymongo.version,
            "httpx": httpx.__version__,
            "uvicorn": uvicorn.__version__,
            "mongodb": base().client.server_info()["version"],
            "so": platform.platform(),
            "api": URL,
        },
        "detalle": sorted(resultados, key=lambda r: (r["usuario"], r["ms"])),
    }
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "rnf01_api.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    resumen = {k: v for k, v in resultado.items() if k not in ("detalle", "referencia_20_consecutivas")}
    resumen["referencia_max_ms_20_consecutivas"] = resultado["referencia_20_consecutivas"]["max_ms"]
    print(json.dumps(resumen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
