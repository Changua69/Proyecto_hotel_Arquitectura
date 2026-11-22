"""Pruebas de latencia contra el despliegue público (Vercel + Render).

Uso (desde la raíz del proyecto, con el entorno virtual activo):
    python -m scripts.medir_latencia_produccion --api https://TU-BACKEND.onrender.com

Opciones:
    --front URL        Frontend en Vercel (por defecto, el del proyecto)
    --usuarios N       Usuarios concurrentes (por defecto 10, como RNF-01)
    --consultas N      Consultas por usuario y en la serie secuencial (por defecto 20)

Qué mide (respuesta HTTP completa desde ESTE computador, en ms):
 0. Arranque en frío: la primera petición a /health. Render Free duerme el servicio cuando no
    recibe tráfico; esa primera respuesta puede tardar decenas de segundos. Se informa aparte y
    NO se mezcla con el resto.
 1. Frontend (Vercel): N cargas seguidas de la página principal.
 2. /health: N peticiones seguidas (API + ping a MongoDB Atlas).
 3. GET /api/disponibilidad: N consultas seguidas (un usuario).
 4. GET /api/disponibilidad: USUARIOS concurrentes x N consultas (escenario de RNF-01; meta p95 <= 2000 ms).

Solo hace consultas (GET): no crea reservas ni modifica datos.
Guarda el resultado en evidencias/semana14/latencia_produccion.json.
"""
import argparse
import json
import math
import platform
import statistics
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

FRONT_POR_DEFECTO = "https://proyecto-hotel-arquitectura-lovat.vercel.app/"
UMBRAL_P95_MS = 2000
EVID = Path(__file__).resolve().parent.parent / "evidencias" / "semana14"


def resumen(muestras: list[dict]) -> dict:
    tiempos = [m["ms"] for m in muestras if m["http"] is not None]
    codigos: dict[str, int] = {}
    for m in muestras:
        clave = str(m["http"]) if m["http"] is not None else "error_red"
        codigos[clave] = codigos.get(clave, 0) + 1
    if not tiempos:
        return {"solicitudes": len(muestras), "codigos": codigos}
    ordenados = sorted(tiempos)
    return {
        "solicitudes": len(muestras),
        "codigos": codigos,
        "min_ms": round(ordenados[0], 1),
        "p50_ms": round(statistics.median(ordenados), 1),
        "p95_ms": round(ordenados[math.ceil(0.95 * len(ordenados)) - 1], 1),
        "max_ms": round(ordenados[-1], 1),
        "promedio_ms": round(statistics.mean(ordenados), 1),
    }


def medir(cliente: httpx.Client, url: str, params: dict | None = None) -> dict:
    t0 = time.perf_counter()
    try:
        r = cliente.get(url, params=params)
        r.read()
        return {"ms": (time.perf_counter() - t0) * 1000, "http": r.status_code}
    except httpx.HTTPError as e:
        return {"ms": (time.perf_counter() - t0) * 1000, "http": None, "error": type(e).__name__}


def parametros(k: int) -> dict:
    # Fechas futuras variadas y los tres tipos; 1 persona cabe en cualquier tipo.
    entrada = date.today() + timedelta(days=30 + k % 60)
    return {"id_tipo": 1 + k % 3, "fecha_entrada": entrada.isoformat(),
            "fecha_salida": (entrada + timedelta(days=2)).isoformat(), "personas": 1}


def serie(cliente, url, n, params_fn=None) -> list[dict]:
    return [medir(cliente, url, params_fn(k) if params_fn else None) for k in range(n)]


def imprimir(titulo: str, r: dict) -> None:
    if "p95_ms" not in r:
        print(f"  {titulo:<42} sin respuestas válidas  {r['codigos']}")
        return
    print(f"  {titulo:<42} p50 {r['p50_ms']:>7} ms   p95 {r['p95_ms']:>7} ms   "
          f"máx {r['max_ms']:>7} ms   códigos {r['codigos']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Latencia del despliegue (Vercel + Render)")
    ap.add_argument("--api", required=True, help="URL del backend en Render, sin barra final")
    ap.add_argument("--front", default=FRONT_POR_DEFECTO)
    ap.add_argument("--usuarios", type=int, default=10)
    ap.add_argument("--consultas", type=int, default=20)
    a = ap.parse_args()
    api = a.api.rstrip("/")
    tiempo_espera = httpx.Timeout(90.0)

    print(f"API: {api}\nFrontend: {a.front}\n")

    with httpx.Client(timeout=tiempo_espera, follow_redirects=True) as c:
        # 0. Arranque en frío
        frio = medir(c, f"{api}/health")
        print(f"0. Arranque en frío (/health, 1.ª petición): {frio['ms']:.0f} ms  HTTP {frio['http']}")
        if frio["http"] is None:
            print(f"   No hubo conexión con la API ({frio.get('error')}). Revise la URL de --api y que el "
                  "servicio esté activo en Render.")
            return
        if frio["http"] != 200:
            print("   La API no respondió 200 en /health. Revise la URL o el estado del servicio en Render.")

        # Comprobación: ¿la base del corte tiene datos?
        prueba = medir(c, f"{api}/api/disponibilidad", parametros(0))
        if prueba["http"] == 404:
            print("\n   /api/disponibilidad respondió 404: la base del corte (marea_test) parece vacía en Atlas.")
            print("   Cárguela una vez:  (PowerShell) $env:MONGO_URI='<cadena de Atlas>'; python -m scripts.reset_db")
            print("                       (Linux)      MONGO_URI='<cadena de Atlas>' python -m scripts.reset_db\n")

        n = a.consultas
        print("\nMidiendo (ya en caliente)...")
        front = serie(c, a.front, n)
        health = serie(c, f"{api}/health", n)
        disp_seq = serie(c, f"{api}/api/disponibilidad", n, parametros)

    # 4. Concurrente
    barrera, concurrente, candado = threading.Barrier(a.usuarios), [], threading.Lock()

    def usuario(u: int) -> None:
        with httpx.Client(timeout=tiempo_espera) as cu:
            barrera.wait()
            for i in range(n):
                m = medir(cu, f"{api}/api/disponibilidad", parametros(u * n + i))
                m["usuario"] = u + 1
                with candado:
                    concurrente.append(m)

    hilos = [threading.Thread(target=usuario, args=(u,)) for u in range(a.usuarios)]
    t0 = time.perf_counter()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    duracion = time.perf_counter() - t0

    r_front, r_health, r_seq, r_conc = map(resumen, (front, health, disp_seq, concurrente))
    cumple = (
        "p95_ms" in r_conc
        and r_conc["p95_ms"] <= UMBRAL_P95_MS
        and set(r_conc["codigos"]) == {"200"}
    )

    print("\nResultados (respuesta HTTP completa, medida desde este computador):")
    imprimir(f"1. Frontend Vercel ({n} seguidas)", r_front)
    imprimir(f"2. /health ({n} seguidas)", r_health)
    imprimir(f"3. /api/disponibilidad ({n} seguidas)", r_seq)
    imprimir(f"4. /api/disponibilidad ({a.usuarios} usuarios x {n})", r_conc)
    print(f"\nRNF-01 en producción (p95 <= {UMBRAL_P95_MS} ms y todas 200): {'CUMPLE' if cumple else 'NO CUMPLE'}")

    resultado = {
        "prueba": "Latencia del despliegue público (Vercel + Render + MongoDB Atlas)",
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "api": api,
        "frontend": a.front,
        "medida": "respuesta HTTP completa desde el cliente, en ms",
        "arranque_en_frio_ms": round(frio["ms"], 1),
        "arranque_en_frio_http": frio["http"],
        "frontend_secuencial": r_front,
        "health_secuencial": r_health,
        "disponibilidad_secuencial": r_seq,
        "disponibilidad_concurrente": {**r_conc, "usuarios": a.usuarios, "consultas_por_usuario": n,
                                        "solicitudes_por_segundo": round(len(concurrente) / duracion, 1)},
        "umbral_p95_ms": UMBRAL_P95_MS,
        "rnf01_cumple": cumple,
        "condiciones": "Cliente en la red del grupo hacia servicios en internet; incluye la latencia de red. "
        "El arranque en frío de Render Free se mide aparte. Solo consultas GET.",
        "cliente": {"so": platform.platform(), "python": platform.python_version(), "httpx": httpx.__version__},
        "detalle_concurrente": sorted(
            [{"usuario": m["usuario"], "ms": round(m["ms"], 1), "http": m["http"]} for m in concurrente],
            key=lambda m: (m["usuario"], m["ms"]),
        ),
    }
    EVID.mkdir(parents=True, exist_ok=True)
    salida = EVID / "latencia_produccion.json"
    salida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
