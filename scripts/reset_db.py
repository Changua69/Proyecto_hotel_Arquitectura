"""Recrea la base de prueba con su estado inicial conocido.

Uso (desde la raíz del proyecto, con el entorno virtual activo):
    python -m scripts.reset_db

Borra y recrea las colecciones del corte (db/esquema.py), carga los datos de prueba
(db/datos_prueba.py) y muestra la verificación. Solo toca la base MONGO_DB_PRUEBA
(por defecto `marea_test`), nunca `hotel_db`. Funciona igual en Windows y Linux (no requiere mongosh).

`reset(completo=False)` es la versión rápida que usan las pruebas entre un caso y otro:
si el esquema ya existe, solo vacía los documentos y vuelve a cargar los datos.
"""
import json

from app.persistence.db import base
from db.datos_prueba import cargar_datos, verificacion

from db.esquema import crear_esquema, esquema_listo, vaciar_colecciones


def reset(verbose: bool = True, completo: bool = True) -> None:
    db = base()
    if completo or not esquema_listo(db):
        crear_esquema(db)
        if verbose:
            print(f"[ok] esquema: colecciones, validadores e índices en '{db.name}'")
    else:
        vaciar_colecciones(db)

from db.esquema import crear_esquema


def reset(verbose: bool = True) -> None:
    db = base()
    crear_esquema(db)
    if verbose:
        print(f"[ok] esquema: colecciones, validadores e índices en '{db.name}'")
        
    cargar_datos(db)
    if verbose:
        print("[ok] datos de prueba")
        print(json.dumps(verificacion(db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    reset()
