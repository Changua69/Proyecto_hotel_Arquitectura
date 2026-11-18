"""Pruebas de extremo a extremo DESDE LA PANTALLA (semana 15).

Recorre la interfaz real en un navegador (Chromium) contra el backend real:
Interfaz -> API -> Servicio -> Repositorio -> MongoDB.

Requisitos (tres terminales):
    1) MongoDB en replica set, datos iniciales y cuentas demo:
         python -m scripts.reset_db
         python -m scripts.crear_usuario --demo
    2) Backend:   uvicorn app.main:app --port 8000
    3) Frontend:  cd frontend && npm run dev          (http://localhost:5173)
    Navegador para las pruebas (una sola vez):
         pip install playwright && python -m playwright install chromium

Uso:
    python -m scripts.e2e_pantalla                    # todos los escenarios
    python -m scripts.e2e_pantalla --ver              # con el navegador visible

Escenarios (se reinicia la base antes de cada uno; nunca toca hotel_db salvo leer el login):
    CA-01 crear reserva válida y confirmar el ID · CA-02 disponibilidad · CA-03 sin disponibilidad
    (también cuando otro usuario toma la última habitación entre la consulta y la confirmación)
    CA-04 rango contiguo · CA-05 capacidad · CA-06 fechas · CA-07/RNF-08 diez usuarios a la vez por la
    última Suite · RNF-01 tiempo de creación visto desde la pantalla · backend caído (sin falsos éxitos)
    · 404 oculta datos anteriores.
Guarda evidencias/semana15/e2e_pantalla.json y capturas en evidencias/semana15/capturas/.
"""
import argparse
import asyncio
import json
import math
import statistics
import time
from datetime import datetime
from pathlib import Path

import httpx

from scripts.reset_db import reset

FRONT = "http://localhost:5173"
API = "http://127.0.0.1:8000"
EVID = Path(__file__).resolve().parent.parent / "evidencias" / "semana15"
CAPT = EVID / "capturas"
CLAVE_DEMO = "Demo1234"  # cuentas demo locales (scripts/crear_usuario.py --demo); no son credenciales reales


def token(email: str) -> str:
    r = httpx.post(f"{API}/login", data={"username": email, "password": CLAVE_DEMO}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def reservar_por_api(tok: str, **cuerpo) -> int:
    base = {"id_huesped": 2, "id_tipo": 3, "numero_personas": 1}
    r = httpx.post(f"{API}/api/reservas", json={**base, **cuerpo}, headers={"Authorization": f"Bearer {tok}"}, timeout=20)
    return r.status_code


class Pantalla:
    def __init__(self, navegador, tok: str, rol: str = "recepcionista", email: str = "recepcion@marea.test"):
        self.nav, self.tok, self.rol, self.email = navegador, tok, rol, email

    async def abrir(self, ruta: str):
        ctx = await self.nav.new_context(viewport={"width": 1360, "height": 900}, accept_downloads=True)
        sesion = json.dumps({"email": self.email, "role": self.rol, "token": self.tok})
        await ctx.add_init_script(f"localStorage.setItem('user', {json.dumps(sesion)})")
        p = await ctx.new_page()
        await p.goto(FRONT + ruta)
        return p


async def llenar_reserva(p, huesped: str, tipo: str, entrada: str, salida: str, personas: str):
    await p.wait_for_selector('#r-huesped:not([disabled]) >> option[value="1"]', state="attached")
    await p.select_option("#r-huesped", huesped)
    await p.select_option("#r-tipo", tipo)
    await p.fill("#r-entrada", entrada)
    await p.fill("#r-salida", salida)
    await p.fill("#r-personas", personas)


async def consultar(p):
    await p.click('button:has-text("Consultar disponibilidad")')
    await p.wait_for_selector('button:has-text("Consultar disponibilidad"):not([disabled])')
    await p.wait_for_selector(".aviso-ok, .aviso-alerta, .aviso-error")


def p95(xs):
    o = sorted(xs)
    return round(o[math.ceil(0.95 * len(o)) - 1], 1)


async def main(ver: bool):
    from playwright.async_api import async_playwright

    CAPT.mkdir(parents=True, exist_ok=True)
    resultados, ok_total = [], True

    def anotar(ca, descripcion, esperado, observado, cumple, captura=None):
        nonlocal ok_total
        ok_total &= cumple
        resultados.append({"escenario": ca, "descripcion": descripcion, "esperado": esperado,
                           "observado": observado, "cumple": cumple, "captura": captura})
        print(f"{'OK ' if cumple else 'NO '} {ca:<8} {descripcion}: {observado}")

    async with async_playwright() as pw:
        nav = await pw.chromium.launch(headless=not ver)
        reset(verbose=False, completo=False)
        tok = token("recepcion@marea.test")
        rec = Pantalla(nav, tok)

        # ---------------- CA-01
        reset(verbose=False, completo=False)
        p = await rec.abrir("/panel/nueva-reserva")
        await llenar_reserva(p, "1", "2", "2026-12-20", "2026-12-23", "3")
        await consultar(p)
        t0 = time.perf_counter()
        await p.click('button:has-text("Confirmar reserva")')
        await p.wait_for_selector("text=/Reserva #\\d+ confirmada/")
        ms = (time.perf_counter() - t0) * 1000
        texto = await p.locator(".aviso-ok").first.inner_text()
        await p.fill('input[aria-label="Id de la reserva"]', "4")
        await p.click('section >> button:has-text("Consultar")')
        await p.wait_for_selector("text=ID confirmado: reserva #4")
        await p.screenshot(path=str(CAPT / "ca01_confirmada.png"), full_page=True)
        anotar("CA-01", "Familiar, 3 personas, 20-23 dic", "Reserva #4 confirmada, habitación 201, $600.000; el ID se confirma",
               f"{texto.splitlines()[0]}; hab. 201={'201' in texto}; total={'$600.000' in texto}; {ms:.0f} ms",
               "Reserva #4 confirmada" in texto and "201" in texto and "$600.000" in texto, "ca01_confirmada.png")
        await p.context.close()

        # ---------------- CA-02
        reset(verbose=False, completo=False)
        p = await rec.abrir("/panel/nueva-reserva")
        await llenar_reserva(p, "1", "3", "2026-12-21", "2026-12-22", "2")
        await consultar(p)
        t = await p.locator(".aviso-ok").inner_text()
        await p.screenshot(path=str(CAPT / "ca02_disponibilidad.png"))
        anotar("CA-02", "Suites 21-22 dic", "302, 303 y 304 (la 301 ocupada no aparece)", t.splitlines()[0],
               "302, 303, 304" in t and "301" not in t, "ca02_disponibilidad.png")
        await p.context.close()

        # ---------------- CA-03 (a) todas ocupadas
        reset(verbose=False, completo=False)
        for _ in range(3):
            reservar_por_api(tok, fecha_entrada="2026-12-21", fecha_salida="2026-12-22")
        p = await rec.abrir("/panel/nueva-reserva")
        await llenar_reserva(p, "1", "3", "2026-12-21", "2026-12-22", "2")
        await consultar(p)
        t = await p.locator(".aviso-alerta").inner_text()
        deshabilitado = await p.is_disabled('button:has-text("Confirmar reserva")')
        await p.screenshot(path=str(CAPT / "ca03_sin_disponibilidad.png"))
        anotar("CA-03", "Suites ocupadas 21-22 dic", "Aviso sin disponibilidad y botón Confirmar deshabilitado",
               f"{t}; confirmar deshabilitado={deshabilitado}", "No hay habitaciones" in t and deshabilitado, "ca03_sin_disponibilidad.png")
        await p.context.close()

        # ---------------- CA-03 (b) la última se ocupa entre la consulta y la confirmación -> 409
        reset(verbose=False, completo=False)
        for _ in range(2):
            reservar_por_api(tok, fecha_entrada="2026-12-21", fecha_salida="2026-12-22")
        p = await rec.abrir("/panel/nueva-reserva")
        await llenar_reserva(p, "1", "3", "2026-12-21", "2026-12-22", "2")
        await consultar(p)
        reservar_por_api(tok, fecha_entrada="2026-12-21", fecha_salida="2026-12-22")  # otro usuario la toma
        antes = httpx.get(f"{API}/api/reservas", headers={"Authorization": f"Bearer {tok}"}).json()
        await p.click('button:has-text("Confirmar reserva")')
        await p.wait_for_selector("aside .aviso-error")
        t = await p.locator("aside .aviso-error").inner_text()
        despues = httpx.get(f"{API}/api/reservas", headers={"Authorization": f"Bearer {tok}"}).json()
        exito_falso = await p.locator("text=/Reserva #\\d+ confirmada/").count()
        await p.screenshot(path=str(CAPT / "ca03_409_desde_pantalla.png"))
        anotar("CA-03b", "La última Suite se ocupa antes de confirmar", "409: aviso claro, sin 'confirmada' y sin reserva nueva",
               f"{t}; reservas {len(antes)}->{len(despues)}; falso éxito={exito_falso}",
               "Ya no hay habitaciones" in t and len(antes) == len(despues) and exito_falso == 0, "ca03_409_desde_pantalla.png")
        await p.context.close()

        # ---------------- CA-04
        reset(verbose=False, completo=False)
        p = await rec.abrir("/panel/nueva-reserva")
        await llenar_reserva(p, "2", "3", "2026-12-23", "2026-12-25", "2")
        await consultar(p)
        await p.click('button:has-text("Confirmar reserva")')
        await p.wait_for_selector("text=/Reserva #\\d+ confirmada/")
        t = await p.locator(".aviso-ok").first.inner_text()
        anotar("CA-04", "Suite desde el 23 (día de salida de la 301)", "Se permite y se asigna la 301",
               " ".join(t.split()[:8]), "301" in t)
        await p.context.close()

        # ---------------- CA-05
        reset(verbose=False, completo=False)
        p = await rec.abrir("/panel/nueva-reserva")
        await llenar_reserva(p, "1", "1", "2026-12-20", "2026-12-22", "3")
        await consultar(p)
        t = await p.locator("form .aviso-error").inner_text()
        await p.screenshot(path=str(CAPT / "ca05_capacidad.png"))
        anotar("CA-05", "Estándar con 3 personas", "422: 'admite como máximo 2 personas', sin reserva", t,
               "máximo 2" in t, "ca05_capacidad.png")
        await p.context.close()

        # ---------------- CA-06
        p = await rec.abrir("/panel/nueva-reserva")
        await llenar_reserva(p, "1", "2", "2026-12-23", "2026-12-20", "2")
        msg = await p.locator(".msg-error").all_inner_texts()
        bloqueado = await p.is_disabled('button:has-text("Consultar disponibilidad")')
        await p.fill("#r-entrada", "2020-01-01")
        await p.fill("#r-salida", "2020-01-03")
        msg2 = await p.locator(".msg-error").all_inner_texts()
        await p.screenshot(path=str(CAPT / "ca06_fechas.png"))
        anotar("CA-06", "Salida antes de la entrada y entrada en el pasado", "Campo marcado y envío bloqueado (el backend además responde 400)",
               f"{msg} / {msg2}; consultar bloqueado={bloqueado}", bloqueado and any("posterior" in m for m in msg) and any("anterior a hoy" in m for m in msg2),
               "ca06_fechas.png")
        await p.context.close()

        # ---------------- CA-07 / RNF-08 desde la pantalla: 10 usuarios por la última Suite
        reset(verbose=False, completo=False)
        for _ in range(3):
            reservar_por_api(tok, fecha_entrada="2026-12-26", fecha_salida="2026-12-28")
        paginas = []
        for i in range(10):
            p = await rec.abrir("/panel/nueva-reserva")
            await llenar_reserva(p, str(1 + i % 3), "3", "2026-12-26", "2026-12-28", "2")
            await consultar(p)
            paginas.append(p)
        vistas = [("304" in await p.locator(".aviso-ok").inner_text()) for p in paginas]
        await asyncio.gather(*(p.click('button:has-text("Confirmar reserva")') for p in paginas))
        await asyncio.gather(*(p.wait_for_selector("aside .aviso-ok, aside .aviso-error") for p in paginas))
        confirmadas = [await p.locator("text=/Reserva #\\d+ confirmada/").count() for p in paginas]
        rechazos = [await p.locator("aside .aviso-error >> text=Ya no hay habitaciones").count() for p in paginas]
        activas = [r for r in httpx.get(f"{API}/api/reservas", params={"desde": "2026-12-26", "hasta": "2026-12-26"},
                                        headers={"Authorization": f"Bearer {tok}"}).json()
                   if r["habitacion"] == "304" and r["estado"] == "CONFIRMADA"]
        await paginas[confirmadas.index(1) if 1 in confirmadas else 0].screenshot(path=str(CAPT / "ca07_ganador.png"))
        await paginas[rechazos.index(1) if 1 in rechazos else 0].screenshot(path=str(CAPT / "ca07_rechazado.png"))
        anotar("CA-07", "10 pantallas confirman a la vez la última Suite (304)",
               "1 'confirmada', 9 'Ya no hay habitaciones', 1 sola reserva activa en la 304",
               f"las 10 vieron la 304={all(vistas)}; confirmadas={sum(confirmadas)}; rechazadas={sum(rechazos)}; activas 304={len(activas)}",
               all(vistas) and sum(confirmadas) == 1 and sum(rechazos) == 9 and len(activas) == 1, "ca07_ganador.png")
        for p in paginas:
            await p.context.close()

        # ---------------- RNF-01: tiempo de creación visto desde la pantalla
        reset(verbose=False, completo=False)
        p = await rec.abrir("/panel/nueva-reserva")
        tiempos_consulta, tiempos_creacion = [], []
        for k in range(10):
            await llenar_reserva(p, str(1 + k % 3), "1", f"2026-12-{10 + k:02d}", f"2026-12-{11 + k:02d}", "1")
            t0 = time.perf_counter()
            await consultar(p)
            tiempos_consulta.append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            await p.click('button:has-text("Confirmar reserva")')
            await p.wait_for_selector("text=/Reserva #\\d+ confirmada/")
            tiempos_creacion.append((time.perf_counter() - t0) * 1000)
            await p.click('button:has-text("Hacer otra reserva")')
        anotar("RNF-01", "Tiempo visto por el usuario (10 consultas y 10 creaciones)", "p95 <= 2000 ms",
               f"consulta p95 {p95(tiempos_consulta)} ms; creación p95 {p95(tiempos_creacion)} ms (media {statistics.mean(tiempos_creacion):.0f} ms)",
               p95(tiempos_consulta) <= 2000 and p95(tiempos_creacion) <= 2000)
        await p.context.close()

        # ---------------- 404 oculta datos anteriores (huéspedes y reservas)
        reset(verbose=False, completo=False)
        p = await rec.abrir("/panel/huespedes")
        await p.wait_for_selector("table.tabla")
        await p.fill('input[aria-label="Consultar huésped por id"]', "1")
        await p.click('button:has-text("Consultar")')
        await p.wait_for_selector("text=ID confirmado: #1")
        await p.keyboard.press("Escape")
        await p.fill('input[aria-label="Consultar huésped por id"]', "999")
        await p.click('button:has-text("Consultar")')
        await p.wait_for_selector("[role=dialog] .aviso-error")
        t = await p.locator("[role=dialog] .aviso-error").inner_text()
        viejos = await p.locator("[role=dialog] >> text=Ana Torres").count()
        await p.screenshot(path=str(CAPT / "huesped_404.png"))
        anotar("404", "Consultar huésped 999 después del 1", "Mensaje 'no existe' y no quedan datos del huésped 1", f"{t}; datos viejos={viejos}",
               "no existe" in t and viejos == 0, "huesped_404.png")
        await p.context.close()

        # ---------------- backend caído: sin falsos éxitos y datos conservados
        p = await rec.abrir("/panel/nueva-reserva")
        await llenar_reserva(p, "1", "2", "2026-12-20", "2026-12-23", "3")
        await consultar(p)
        await p.route("**/api/reservas", lambda r: r.abort("connectionrefused"))
        await p.click('button:has-text("Confirmar reserva")')
        await p.wait_for_selector("aside .aviso-alerta")
        t = await p.locator("aside .aviso-alerta").inner_text()
        falso = await p.locator("text=/Reserva #\\d+ confirmada/").count()
        conservado = await p.input_value("#r-personas") == "3"
        await p.screenshot(path=str(CAPT / "backend_caido.png"))
        anotar("Caída", "El backend no responde al confirmar", "Aviso comprensible, sin 'confirmada', datos conservados",
               f"{t.splitlines()[0]}; falso éxito={falso}; datos conservados={conservado}",
               "No se pudo conectar" in t and falso == 0 and conservado, "backend_caido.png")
        await p.context.close()

        await nav.close()
    reset(verbose=False, completo=False)

    EVID.mkdir(parents=True, exist_ok=True)
    salida = {
        "prueba": "Extremo a extremo desde la pantalla (Interfaz -> API -> Servicio -> Repositorio -> MongoDB)",
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "frontend": FRONT, "api": API, "navegador": "Chromium (Playwright)",
        "todos_cumplen": ok_total, "escenarios": resultados,
    }
    (EVID / "e2e_pantalla.json").write_text(json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'TODOS CUMPLEN' if ok_total else 'HAY ESCENARIOS QUE NO CUMPLEN'} · evidencias/semana15/e2e_pantalla.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Pruebas de extremo a extremo desde la pantalla")
    ap.add_argument("--ver", action="store_true", help="Mostrar el navegador")
    asyncio.run(main(ap.parse_args().ver))
