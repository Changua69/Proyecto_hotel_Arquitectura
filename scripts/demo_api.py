"""Demostración de los contratos por API (semana 14).

Uso:  python -m scripts.demo_api

Recrea la base, ejecuta cada ejemplo del contrato contra la API real y escribe las
solicitudes y respuestas obtenidas en evidencias/semana14/contratos_ejemplos.md.
Así los ejemplos del README coinciden con lo que el backend responde de verdad.
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import app
from scripts.reset_db import reset

EVID = Path(__file__).resolve().parent.parent / "evidencias" / "semana14"

CASOS = [
    ("RF-02 válido (CA-02): Suites libres del 21 al 22 de diciembre", "GET",
     "/api/disponibilidad?id_tipo=3&fecha_entrada=2026-12-21&fecha_salida=2026-12-22&personas=2", None),
    ("RF-02 capacidad excedida (CA-05)", "GET",
     "/api/disponibilidad?id_tipo=1&fecha_entrada=2026-12-20&fecha_salida=2026-12-23&personas=3", None),
    ("RF-04 válido (CA-01): Familiar para 3 personas del 20 al 23 de diciembre", "POST", "/api/reservas",
     {"id_huesped": 1, "id_tipo": 2, "fecha_entrada": "2026-12-20", "fecha_salida": "2026-12-23", "numero_personas": 3}),
    ("RF-04 confirmación: consultar la reserva creada", "GET", "/api/reservas/4", None),
    ("RF-04 reserva inexistente", "GET", "/api/reservas/999999", None),
    ("RF-04 id inválido", "GET", "/api/reservas/abc", None),
    ("RF-04 fechas inválidas (CA-06)", "POST", "/api/reservas",
     {"id_huesped": 1, "id_tipo": 2, "fecha_entrada": "2026-12-23", "fecha_salida": "2026-12-20", "numero_personas": 2}),
    ("RF-04 huésped inexistente", "POST", "/api/reservas",
     {"id_huesped": 999, "id_tipo": 2, "fecha_entrada": "2026-12-20", "fecha_salida": "2026-12-23", "numero_personas": 2}),
    ("RF-04 campo obligatorio ausente", "POST", "/api/reservas",
     {"id_tipo": 2, "fecha_entrada": "2026-12-20", "fecha_salida": "2026-12-23", "numero_personas": 2}),
    ("RF-04 sin disponibilidad (CA-03): se ocupan 302, 303 y 304 y se pide otra Suite", "POST*3+1", "/api/reservas",
     {"id_huesped": 2, "id_tipo": 3, "fecha_entrada": "2026-12-21", "fecha_salida": "2026-12-22", "numero_personas": 2}),
]


def main() -> None:
    reset(verbose=False)
    api = TestClient(app)
    partes = ["# Ejemplos de contrato ejecutados contra el backend (semana 14)\n",
              "Generado con `python -m scripts.demo_api` sobre la base de prueba recién creada.\n"]
    for titulo, metodo, ruta, cuerpo in CASOS:
        if metodo == "POST*3+1":
            for _ in range(3):
                api.post(ruta, json=cuerpo)
            metodo = "POST"
        r = api.request(metodo, ruta, json=cuerpo)
        print(f"{r.status_code}  {metodo} {ruta}")
        partes.append(f"\n## {titulo}\n\n```http\n{metodo} {ruta}\n")
        if cuerpo is not None:
            partes.append("Content-Type: application/json\n\n" + json.dumps(cuerpo, ensure_ascii=False, indent=2) + "\n")
        partes.append("```\n\n```http\n")
        partes.append(f"HTTP {r.status_code} {r.reason_phrase}\n")
        if "location" in r.headers:
            partes.append(f"Location: {r.headers['location']}\n")
        partes.append("\n" + json.dumps(r.json(), ensure_ascii=False, indent=2) + "\n```\n")
    reset(verbose=False)
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "contratos_ejemplos.md").write_text("".join(partes), encoding="utf-8")
    print(f"\nEjemplos guardados en {EVID / 'contratos_ejemplos.md'}")


if __name__ == "__main__":
    main()
