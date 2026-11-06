"""Recrea la base de prueba con su estado inicial conocido.

Uso (desde la raíz del proyecto, con el entorno virtual activo):
    python -m scripts.reset_db

Ejecuta db/01_schema.sql y db/02_seed.sql y muestra la verificación de db/03_verificacion.sql.
Funciona igual en Windows y Linux (no requiere psql).
"""
from pathlib import Path

from app.persistence.db import unidad_de_trabajo

DB_DIR = Path(__file__).resolve().parent.parent / "db"


def reset(url: str | None = None, verbose: bool = True) -> None:
    with unidad_de_trabajo(url) as conn:
        for nombre in ("01_schema.sql", "02_seed.sql"):
            conn.execute((DB_DIR / nombre).read_text(encoding="utf-8"))
            if verbose:
                print(f"[ok] {nombre}")
    if verbose:
        with unidad_de_trabajo(url) as conn:
            for sql in (DB_DIR / "03_verificacion.sql").read_text(encoding="utf-8").split(";"):
                lineas = [l for l in sql.splitlines() if l.strip() and not l.strip().startswith("--")]
                if lineas:
                    for fila in conn.execute("\n".join(lineas)).fetchall():
                        print("     ", dict(fila))


if __name__ == "__main__":
    reset()
