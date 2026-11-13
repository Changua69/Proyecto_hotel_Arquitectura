import pytest

from scripts.reset_db import reset


@pytest.fixture(autouse=True)
def base_limpia():
    """Cada prueba arranca desde el estado inicial conocido (db/esquema.py + db/datos_prueba.py)."""
    reset(verbose=False)
    yield
