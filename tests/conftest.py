import pytest


@pytest.fixture(scope="session")
def esquema_recreado():
    """Una sola vez por corrida: borra y recrea colecciones, validadores e índices."""
    from scripts.reset_db import reset

    reset(verbose=False, completo=True)


@pytest.fixture(autouse=True)
def base_limpia(request):
    """Cada prueba con base real arranca desde el estado inicial conocido
    (db/esquema.py + db/datos_prueba.py). Entre pruebas solo se vacían y recargan los
    documentos: recrear las colecciones cientos de veces agota los archivos abiertos de MongoDB.

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

    request.getfixturevalue("esquema_recreado")
    reset(verbose=False, completo=False)
    yield
