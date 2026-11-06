import pytest

from scripts.reset_db import reset


@pytest.fixture(autouse=True)
def base_limpia():
    """Cada prueba arranca desde el estado inicial conocido (db/01 + db/02)."""
    reset(verbose=False)
    yield
