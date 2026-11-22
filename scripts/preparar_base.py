"""Prepara la base del corte SIN BORRAR NADA (pensado para producción / Atlas).

Uso (desde la raíz del proyecto, con el entorno virtual activo):
    python -m scripts.preparar_base

- Crea las colecciones, validadores e índices que falten.
- Carga los 3 tipos y las 24 habitaciones solo si todavía no existen.
- NO carga huéspedes ni reservas de prueba y NO borra datos (a diferencia de reset_db).
El backend hace esto mismo al arrancar, así que en Render basta con desplegar.
"""
import json

from app.persistence.db import base
from db.datos_prueba import cargar_catalogo_si_falta, verificacion
from db.esquema import asegurar_esquema


def preparar(verbose: bool = True) -> list[str]:
    db = base()
    cambios = asegurar_esquema(db) + cargar_catalogo_si_falta(db)
    if verbose:
        print(f"Base: {db.name}")
        print("\n".join(f"[ok] {c}" for c in cambios) or "[ok] nada que hacer: la base ya estaba lista")
        print(json.dumps(verificacion(db), ensure_ascii=False, indent=2))
    return cambios


if __name__ == "__main__":
    preparar()
