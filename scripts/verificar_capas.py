"""Verificación de RNF-06 (mantenibilidad / modularidad).

Uso:  python -m scripts.verificar_capas

Busca acceso directo a MongoDB (pymongo, bson, MongoClient, colecciones u operaciones
como find/insert_one/aggregate) fuera de app/persistence/ y db/. Resultado esperado: 0 hallazgos.

Las rutas heredadas (app/routes, app/database.py, app/init_rooms.py) todavía usan MongoDB
directamente: se listan aparte como PENDIENTES porque se reemplazan en la semana 2 por
endpoints que llaman a los servicios. No se ocultan.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PATRON_PY = re.compile(
    r"\b(pymongo|bson|MongoClient|\w+_collection)\b"
    r"|\.(find|find_one|insert_one|insert_many|update_one|update_many|replace_one|delete_one|delete_many"
    r"|aggregate|count_documents|distinct|find_one_and_update|bulk_write)\("
)
PATRON_FRONT = re.compile(r"\b(mongodb|mongoose|MongoClient)\b")
PERMITIDOS = {RAIZ / "app" / "persistence", RAIZ / "db", RAIZ / "scripts", RAIZ / "tests"}
HEREDADOS = {RAIZ / "app" / "routes", RAIZ / "app" / "database.py", RAIZ / "app" / "init_rooms.py"}


def _en(f: Path, rutas: set[Path]) -> bool:
    return any(f == p or p in f.parents for p in rutas)


def main() -> int:
    hallazgos, heredados = [], set()
    archivos = [(f, PATRON_PY) for f in (RAIZ / "app").rglob("*.py")]
    archivos += [(f, PATRON_FRONT) for f in (RAIZ / "frontend" / "src").rglob("*.ts*")]
    for f, patron in archivos:
        if _en(f, PERMITIDOS):
            continue
        for n, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if patron.search(linea):
                if _en(f, HEREDADOS):
                    heredados.add(str(f.relative_to(RAIZ)))
                else:
                    hallazgos.append(f"{f.relative_to(RAIZ)}:{n}: {linea.strip()}")
    if hallazgos:
        print("\n".join(hallazgos))
    else:
        print("OK: no hay acceso a MongoDB fuera de app/persistence en el código del corte (0 hallazgos)")
    if heredados:
        print(f"PENDIENTE semana 2 ({len(heredados)} archivos heredados con acceso directo a MongoDB):")
        print("\n".join(f"  - {h}" for h in sorted(heredados)))
    return 1 if hallazgos else 0


if __name__ == "__main__":
    sys.exit(main())
