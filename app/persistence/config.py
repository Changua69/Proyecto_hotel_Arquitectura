"""Configuración de la conexión a PostgreSQL.

La URL se lee de la variable de entorno DATABASE_URL (o del archivo .env).
Nunca se escriben credenciales reales en el código.
"""
import os

try:  # python-dotenv es opcional
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

DEFAULT_URL = "postgresql://marea:marea_dev@localhost:5432/marea_test"


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_URL)
