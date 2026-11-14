import pytest


@pytest.fixture(autouse=True)
def base_limpia(request):
    """Cada prueba con base real arranca desde el estado inicial conocido
    (db/esquema.py + db/datos_prueba.py).

    Las pruebas marcadas `sin_base` (servicios aislados, RNF-06) no tocan MongoDB:
    para ellas no se reinicia nada y cualquier intento de conexión falla."""
    if request.node.get_closest_marker("sin_base"):
        import pymongo

        def _prohibido(*args, **kwargs):
            raise AssertionError("Una prueba aislada intentó abrir una conexión real a MongoDB")

        mp = pytest.MonkeyPatch()
        mp.setattr(pymongo.MongoClient, "__init__", _prohibido)
        mp.setattr("app.persistence.db._cliente", None)  # ni siquiera el cliente compartido
        yield
        mp.undo()
        return

    from scripts.reset_db import reset

    reset(verbose=False)
    yield
