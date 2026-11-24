"""Latencia de MODIFICAR RESERVA (PUT /api/reservas/{id}) y persistencia bajo carga.

Uso LOCAL (levanta la API en este proceso; RECREA la base marea_test):
    python -m scripts.medir_modificar

Uso contra el DESPLIEGUE (Render + Atlas). Crea reservas de prueba lejanas y las CANCELA al final:
    python -m scripts.medir_modificar --api https://TU-API.onrender.com --email recepcion@x.com --password ... --yes
    (o con un token ya obtenido:  --token eyJ...)

Opciones:  --usuarios 10  --por-usuario 10  --secuencial 20  --huesped 1

Qué mide (respuesta HTTP completa desde el cliente, en ms; 1 solicitud de calentamiento excluida):
  A. LECTURA base:       GET /api/reservas/{id}, 1 usuario            (referencia: costo sin escritura)
  B. MODIFICAR secuencial: PUT alternando fechas, 1 usuario
  C. MODIFICAR concurrente: N usuarios a la vez, cada uno sobre SU reserva, K modificaciones c/u
  Diferencia B - A = lo que cuesta la transacción de escritura (write concern "majority").
  Meta: p95 <= 2000 ms y todas 200 (la misma de RNF-01).

Persistencia bajo carga: al terminar, vuelve a LEER cada reserva y comprueba que lo guardado es
exactamente lo último que respondió 200 la API (si no coincide, se pierde una actualización).

Guarda el resultado en evidencias/modificar/latencia_modificar.json.
"""
import argparse
import json
import math
import os
import platform
import statistics
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

UMBRAL_P95_MS = 2000
EVID = Path(__file__).resolve().parent.parent / "evidencias" / "modificar"
HOST, PUERTO = "127.0.0.1", 8002


# ------------------------------------------------------------------ estadística
def resumen(muestras: list[dict]) -> dict:
    tiempos = sorted(m["ms"] for m in muestras)
    codigos: dict[str, int] = {}
    for m in muestras:
        k = str(m["http"]) if m["http"] is not None else "error_red"
        codigos[k] = codigos.get(k, 0) + 1
    if not tiempos:
        return {"solicitudes": 0, "codigos": codigos}
    return {
        "solicitudes": len(tiempos), "codigos": codigos,
        "min_ms": round(tiempos[0], 1), "p50_ms": round(statistics.median(tiempos), 1),
        "p95_ms": round(tiempos[math.ceil(0.95 * len(tiempos)) - 1], 1),
        "max_ms": round(tiempos[-1], 1), "promedio_ms": round(statistics.mean(tiempos), 1),
    }


def imprimir(titulo: str, r: dict) -> None:
    if "p95_ms" not in r:
        print(f"  {titulo:<40} sin respuestas   {r['codigos']}")
        return
    print(f"  {titulo:<40} p50 {r['p50_ms']:>7} ms  p95 {r['p95_ms']:>7} ms  máx {r['max_ms']:>7} ms  {r['codigos']}")


# ------------------------------------------------------------------ cliente
class Api:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.h = {"Authorization": f"Bearer {token}"}

    def llamar(self, c: httpx.Client, metodo: str, ruta: str, **kw) -> dict:
        t0 = time.perf_counter()
        try:
            r = c.request(metodo, self.url + ruta, headers=self.h, **kw)
            r.read()
            return {"ms": (time.perf_counter() - t0) * 1000, "http": r.status_code, "r": r}
        except httpx.HTTPError as e:
            return {"ms": (time.perf_counter() - t0) * 1000, "http": None, "error": type(e).__name__, "r": None}


def levantar_local():
    """API del corte dentro de este proceso (mismo patrón de scripts/medir_api.py). Devuelve (servidor, token)."""
    import uvicorn

    os.environ.setdefault("SECRET_KEY", "clave-solo-para-mediciones")
    from app.api.app import app
    from app.auth.jwt_handler import create_access_token
    from scripts.reset_db import reset

    reset(verbose=False)  # ⚠ borra y recrea marea_test
    srv = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PUERTO, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("La API local no arrancó")
    return srv, create_access_token({"sub": "recepcion@marea.test", "role": "recepcionista"})


# ------------------------------------------------------------------ escenario
def variantes(inicio: date) -> list[tuple[date, date, int]]:
    """Dos configuraciones que se alternan (siempre distintas de la anterior)."""
    return [(inicio, inicio + timedelta(days=3), 2), (inicio, inicio + timedelta(days=2), 1)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Latencia de PUT /api/reservas/{id}")
    ap.add_argument("--api", help="URL del backend desplegado. Si se omite, se prueba en local.")
    ap.add_argument("--token")
    ap.add_argument("--email")
    ap.add_argument("--password")
    ap.add_argument("--huesped", type=int, default=1, help="id del huésped dueño de las reservas de prueba")
    ap.add_argument("--usuarios", type=int, default=10)
    ap.add_argument("--por-usuario", type=int, default=10)
    ap.add_argument("--secuencial", type=int, default=20)
    ap.add_argument("--yes", action="store_true", help="Confirma que se crearán/cancelarán reservas en el despliegue")
    a = ap.parse_args()

    servidor = None
    if a.api:
        if not a.yes:
            print("Esto crea reservas de prueba (lejanas) en el despliegue y las cancela al final.\n"
                  "Repita el comando con --yes para continuar.")
            return
        url, token = a.api, a.token
        if not token:
            if not (a.email and a.password):
                print("Falta --token o --email y --password de una cuenta de recepción/admin.")
                return
            with httpx.Client(timeout=90) as c:
                r = c.post(url.rstrip("/") + "/login", data={"username": a.email, "password": a.password})
            if r.status_code != 200:
                print(f"Login rechazado (HTTP {r.status_code}).")
                return
            token = r.json()["access_token"]
    else:
        servidor, token = levantar_local()
        url = f"http://{HOST}:{PUERTO}"

    from app.services.reloj import hoy_hotel

    api = Api(url, token)
    base_fecha = hoy_hotel() + timedelta(days=180)   # lejos de reservas reales
    creadas: list[int] = []
    timeout = httpx.Timeout(90.0)

    def crear(c: httpx.Client, inicio: date) -> int:
        m = api.llamar(c, "POST", "/api/reservas", json={
            "id_huesped": a.huesped, "id_tipo": 1, "fecha_entrada": inicio.isoformat(),
            "fecha_salida": (inicio + timedelta(days=2)).isoformat(), "numero_personas": 1})
        if m["http"] != 201:
            raise SystemExit(f"No se pudo crear la reserva de prueba (HTTP {m['http']}): "
                             f"{m['r'].text if m['r'] is not None else m.get('error')}")
        idr = m["r"].json()["id_reserva"]
        creadas.append(idr)
        return idr

    ultimo: dict[int, tuple[str, str, int]] = {}      # lo último que la API confirmó con 200, por reserva
    candado = threading.Lock()

    def modificar(c: httpx.Client, idr: int, inicio: date, i: int) -> dict:
        ent, sal, pers = variantes(inicio)[i % 2]
        m = api.llamar(c, "PUT", f"/api/reservas/{idr}", json={
            "fecha_entrada": ent.isoformat(), "fecha_salida": sal.isoformat(), "numero_personas": pers})
        if m["http"] == 200:
            with candado:
                ultimo[idr] = (ent.isoformat(), sal.isoformat(), pers)
        return m

    try:
        with httpx.Client(timeout=timeout) as c:
            print(f"API: {url}\nMidiendo...\n")
            # --- preparación (no se mide)
            ids_seq = crear(c, base_fecha)
            ids_users = [crear(c, base_fecha + timedelta(days=10 * (u + 1))) for u in range(a.usuarios)]
            api.llamar(c, "GET", f"/api/reservas/{ids_seq}")                 # calentamiento
            modificar(c, ids_seq, base_fecha, 0)

            # --- A. lectura base
            lect = []
            for _ in range(a.secuencial):
                m = api.llamar(c, "GET", f"/api/reservas/{ids_seq}")
                lect.append({"ms": m["ms"], "http": m["http"]})

            # --- B. modificar secuencial
            seq = []
            for i in range(a.secuencial):
                m = modificar(c, ids_seq, base_fecha, i + 1)
                seq.append({"ms": m["ms"], "http": m["http"]})

        # --- C. modificar concurrente
        barrera, conc = threading.Barrier(a.usuarios), []

        def usuario(u: int) -> None:
            inicio = base_fecha + timedelta(days=10 * (u + 1))
            with httpx.Client(timeout=timeout) as cu:
                barrera.wait()
                for i in range(a.por_usuario):
                    m = modificar(cu, ids_users[u], inicio, i + 1)
                    with candado:
                        conc.append({"ms": m["ms"], "http": m["http"]})

        t0 = time.perf_counter()
        hilos = [threading.Thread(target=usuario, args=(u,)) for u in range(a.usuarios)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        duracion = time.perf_counter() - t0

        # --- persistencia bajo carga: lo guardado == lo último confirmado
        discrepancias = []
        with httpx.Client(timeout=timeout) as c:
            for idr, (ent, sal, pers) in ultimo.items():
                g = api.llamar(c, "GET", f"/api/reservas/{idr}")
                if g["http"] != 200:
                    discrepancias.append({"reserva": idr, "motivo": f"GET {g['http']}"})
                    continue
                d = g["r"].json()
                if (d["fecha_entrada"], d["fecha_salida"], d["numero_personas"]) != (ent, sal, pers):
                    discrepancias.append({"reserva": idr, "esperado": [ent, sal, pers],
                                          "guardado": [d["fecha_entrada"], d["fecha_salida"], d["numero_personas"]]})
    finally:
        # --- limpieza
        if a.api and creadas:
            with httpx.Client(timeout=timeout) as c:
                for idr in creadas:
                    api.llamar(c, "POST", f"/api/reservas/{idr}/cancelar")
            print(f"(Se cancelaron {len(creadas)} reservas de prueba en el despliegue.)")
        if servidor is not None:
            servidor.should_exit = True
            time.sleep(0.3)
            from scripts.reset_db import reset
            reset(verbose=False)

    r_lect, r_seq, r_conc = resumen(lect), resumen(seq), resumen(conc)
    cumple = ("p95_ms" in r_conc and r_conc["p95_ms"] <= UMBRAL_P95_MS and set(r_conc["codigos"]) == {"200"})
    print("Resultados (HTTP completo medido desde este computador):")
    imprimir(f"A. GET reserva ({a.secuencial} seguidas)", r_lect)
    imprimir(f"B. PUT modificar ({a.secuencial} seguidas)", r_seq)
    imprimir(f"C. PUT modificar ({a.usuarios} usuarios x {a.por_usuario})", r_conc)
    if "p50_ms" in r_lect and "p50_ms" in r_seq:
        print(f"\n  Costo de escribir (p50 PUT - p50 GET): {r_seq['p50_ms'] - r_lect['p50_ms']:.1f} ms")
    print(f"  Solicitudes por segundo (C): {len(conc) / duracion:.1f}")
    print(f"\n  Persistencia bajo carga: {'OK, lo guardado = lo último confirmado' if not discrepancias else 'DISCREPANCIAS'}"
          f" ({len(ultimo)} reservas revisadas)")
    for d in discrepancias:
        print("   ", d)
    print(f"\n  Latencia (p95 <= {UMBRAL_P95_MS} ms y todas 200): {'CUMPLE' if cumple else 'NO CUMPLE'}")

    EVID.mkdir(parents=True, exist_ok=True)
    salida = EVID / "latencia_modificar.json"
    salida.write_text(json.dumps({
        "prueba": "Latencia de PUT /api/reservas/{id} y persistencia bajo carga",
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "api": url, "modo": "despliegue" if a.api else "local",
        "lectura_base": r_lect, "modificar_secuencial": r_seq,
        "modificar_concurrente": {**r_conc, "usuarios": a.usuarios, "por_usuario": a.por_usuario,
                                  "solicitudes_por_segundo": round(len(conc) / duracion, 1)},
        "umbral_p95_ms": UMBRAL_P95_MS, "cumple": cumple,
        "persistencia_bajo_carga": {"reservas_revisadas": len(ultimo), "discrepancias": discrepancias,
                                    "ok": not discrepancias},
        "cliente": {"so": platform.platform(), "python": platform.python_version(), "httpx": httpx.__version__},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
