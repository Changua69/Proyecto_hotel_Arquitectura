"""CRUD de huéspedes — servicio aislado (semana 15, RNF-06).

GestionHuespedesService se prueba con un repositorio en memoria: sin MongoDB.
Ejecutar:  pytest -v tests/test_huespedes_servicio.py
"""
import pytest

from app.persistence.errors import DuplicadoError
from app.persistence.models import Huesped
from app.services.errores import (
    DatoDuplicadoError,
    EntradaInvalidaError,
    HuespedConReservasError,
    NoEncontradoError,
)
from app.services.huespedes import DatosHuesped, GestionHuespedesService

pytestmark = pytest.mark.sin_base


class HuespedesEnMemoria:
    def __init__(self):
        self.datos: dict[int, Huesped] = {1: Huesped(1, "Ana Torres", "1020304050", "Colombiana", None, "ana@example.com")}
        self.activas: dict[int, int] = {}
        self.llamadas: list[str] = []

    def _unico(self, h, excepto=None):
        for i, x in self.datos.items():
            if i == excepto:
                continue
            if x.documento == h.documento:
                raise DuplicadoError("documento")
            if h.correo and (x.correo or "").lower() == h.correo.lower():
                raise DuplicadoError("correo")

    def obtener_por_id(self, i):
        return self.datos.get(i)

    def listar(self, buscar=None):
        b = (buscar or "").lower()
        return sorted((h for h in self.datos.values()
                       if not b or b in h.nombre.lower() or b in h.documento or b in (h.correo or "")),
                      key=lambda h: h.nombre)

    def crear(self, h):
        self.llamadas.append("crear")
        self._unico(h)
        i = max(self.datos, default=0) + 1
        self.datos[i] = Huesped(i, h.nombre, h.documento, h.nacionalidad, h.telefono, h.correo)
        return i

    def actualizar(self, i, h):
        self.llamadas.append("actualizar")
        if i not in self.datos:
            return False
        self._unico(h, excepto=i)
        self.datos[i] = Huesped(i, h.nombre, h.documento, h.nacionalidad, h.telefono, h.correo)
        return True

    def eliminar(self, i):
        self.llamadas.append("eliminar")
        return self.datos.pop(i, None) is not None

    def contar_reservas_activas(self, i):
        return self.activas.get(i, 0)


class Repos:
    def __init__(self, h):
        self.huespedes = h


class Proveedor:
    def __init__(self):
        self.h = HuespedesEnMemoria()

    def leer(self, fn):
        return fn(Repos(self.h))

    def escribir(self, fn):
        return fn(Repos(self.h))


@pytest.fixture
def p():
    return Proveedor()


@pytest.fixture
def s(p):
    return GestionHuespedesService(p)


def test_crear_normaliza_y_retorna_lo_guardado(s):
    h = s.crear(DatosHuesped("  María   Gómez ", "10334-455", " ", None, "  MARIA@Example.com "))
    assert (h.id_huesped, h.nombre, h.documento, h.nacionalidad, h.correo) == (2, "María Gómez", "10334-455", None, "maria@example.com")


def test_crear_reune_todos_los_errores_y_no_guarda(s, p):
    with pytest.raises(EntradaInvalidaError) as e:
        s.crear(DatosHuesped("A", "ab", "x" * 51, "12", "no-es-correo"))
    campos = {x["campo"] for x in e.value.errores}
    assert campos == {"nombre", "documento", "nacionalidad", "telefono", "correo"}
    assert "crear" not in p.h.llamadas


@pytest.mark.parametrize("campo, datos", [
    ("documento", DatosHuesped("Otra", "1020304050")),
    ("correo", DatosHuesped("Otra", "999888", correo="ANA@example.com")),
])
def test_crear_duplicado_409_indica_el_campo(s, campo, datos):
    with pytest.raises(DatoDuplicadoError) as e:
        s.crear(datos)
    assert e.value.campo == campo and e.value.http == 409


def test_actualizar_inexistente_404(s):
    with pytest.raises(NoEncontradoError):
        s.actualizar(99, DatosHuesped("Nadie", "123456"))


def test_actualizar_conserva_su_propio_documento(s):
    h = s.actualizar(1, DatosHuesped("Ana T.", "1020304050", correo="ana@example.com"))
    assert h.nombre == "Ana T."


def test_eliminar_con_reservas_activas_409_y_no_borra(s, p):
    p.h.activas[1] = 2
    with pytest.raises(HuespedConReservasError):
        s.eliminar(1)
    assert 1 in p.h.datos and "eliminar" not in p.h.llamadas


def test_eliminar_inexistente_404(s):
    with pytest.raises(NoEncontradoError):
        s.eliminar(50)


@pytest.mark.parametrize("id_malo", [0, -3])
def test_id_no_positivo_400(s, id_malo):
    with pytest.raises(EntradaInvalidaError):
        s.obtener(id_malo)


def test_ficha_por_correo_exacto(s):
    assert s.obtener_por_correo("Ana@Example.com").id_huesped == 1
    assert s.obtener_por_correo("a@example.com") is None
