"""Configuración de la conexión a MongoDB.

Variables (en el entorno o en el archivo .env):
  MONGO_URI        URI del servidor. Debe ser un replica set (aunque sea de un solo nodo),
                   porque las transacciones de MongoDB solo existen en replica sets.
  MONGO_DB_PRUEBA  Base de la persistencia del corte vertical. Es DISTINTA de `hotel_db`
                   (la de las rutas heredadas) porque `reset_db` borra y recrea sus colecciones.
Nunca se escriben credenciales reales en el código.
"""
import os

try:  # python-dotenv es opcional
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

DEFAULT_URI = "mongodb://127.0.0.1:27017/?replicaSet=rs0"
DEFAULT_DB = "marea_test"


def mongo_uri() -> str:
    return os.getenv("MONGO_URI", DEFAULT_URI)


def nombre_base() -> str:
    return os.getenv("MONGO_DB_PRUEBA", DEFAULT_DB)
