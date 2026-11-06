"""Verificación de RNF-06 (mantenibilidad / modularidad).

Uso:  python -m scripts.verificar_capas

Busca sentencias SQL fuera de app/persistence/ y db/. Resultado esperado: 0 hallazgos.
(Las rutas Mongo heredadas en app/routes no usan SQL; se reemplazan en la semana 2.)
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PATRON = re.compile(r"\b(SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b", re.I)
PERMITIDOS = {RAIZ / "app" / "persistence", RAIZ / "db", RAIZ / "scripts", RAIZ / "tests"}


def main() -> int:
    hallazgos = []
    for f in list((RAIZ / "app").rglob("*.py")) + list((RAIZ / "frontend" / "src").rglob("*.ts*")):
        if any(p in f.parents for p in PERMITIDOS):
            continue
        for n, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if PATRON.search(linea):
                hallazgos.append(f"{f.relative_to(RAIZ)}:{n}: {linea.strip()}")
    print("\n".join(hallazgos) if hallazgos else "OK: no hay SQL fuera de app/persistence (0 hallazgos)")
    return 1 if hallazgos else 0


if __name__ == "__main__":
    sys.exit(main())
