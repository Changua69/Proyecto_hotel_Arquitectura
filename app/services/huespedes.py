"""Servicio de gestión de huéspedes (semana 15): CRUD completo.

Capa de servicio: valida y normaliza los datos, aplica las reglas y traduce los errores de
persistencia a errores de negocio. No conoce HTTP ni MongoDB (usa ProveedorRepositorios).

Reglas:
- Nombre 2–100 caracteres; documento 3–30 (letras, números, punto o guion), único.
- Correo opcional con formato válido, único sin distinguir mayúsculas; se guarda en minúsculas.
- Teléfono opcional: 7–20 dígitos, espacios y '+' inicial. Nacionalidad opcional (≤ 50).
- No se elimina un huésped con reservas activas (CONFIRMADA o EN_CURSO): se conservaría una
  reserva que apunta a un huésped inexistente.
"""
import re
from dataclasses import dataclass

from app.persistence.errors import DatosInvalidosError as DatosRechazadosPorBD
from app.persistence.errors import DuplicadoError
from app.persistence.models import Huesped, NuevoHuesped
from app.persistence.proveedor import ProveedorRepositorios
from app.services.errores import (
    DatoDuplicadoError,
    EntradaInvalidaError,
    HuespedConReservasError,
    NoEncontradoError,
)

MSG_NO_EXISTE = "El huésped no existe."
MSG_DUPLICADO = {
    "documento": "Ya existe un huésped con ese documento.",
    "correo": "Ya existe un huésped con ese correo.",
}
MSG_CON_RESERVAS = "No se puede eliminar: el huésped tiene {n} reserva(s) activa(s)."

_RE_DOCUMENTO = re.compile(r"^[A-Za-z0-9.\-]{3,30}$")
_RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RE_TELEFONO = re.compile(r"^\+?[0-9 ]{7,20}$")


@dataclass(frozen=True)
class DatosHuesped:
    """Lo que llega desde la API (sin validar)."""

    nombre: str
    documento: str
    nacionalidad: str | None = None
    telefono: str | None = None
    correo: str | None = None


def _limpio(v: str | None) -> str | None:
    """Quita espacios a los lados; un texto vacío se trata como 'sin dato'."""
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


def validar(datos: DatosHuesped) -> NuevoHuesped:
    """Normaliza y valida. Reúne TODOS los errores para que la pantalla los marque a la vez."""
    nombre = _limpio(datos.nombre) or ""
    documento = (_limpio(datos.documento) or "").replace(" ", "")
    nacionalidad = _limpio(datos.nacionalidad)
    telefono = _limpio(datos.telefono)
    correo = _limpio(datos.correo)
    correo = correo.lower() if correo else None

    errores: list[dict] = []

    def error(campo: str, mensaje: str) -> None:
        errores.append({"campo": campo, "mensaje": mensaje})

    if not nombre:
        error("nombre", "es obligatorio")
    elif not 2 <= len(nombre) <= 100:
        error("nombre", "debe tener entre 2 y 100 caracteres")
    if not documento:
        error("documento", "es obligatorio")
    elif not _RE_DOCUMENTO.match(documento):
        error("documento", "debe tener 3 a 30 letras, números, puntos o guiones")
    if nacionalidad and len(nacionalidad) > 50:
        error("nacionalidad", "debe tener máximo 50 caracteres")
    if telefono and not _RE_TELEFONO.match(telefono):
        error("telefono", "debe tener 7 a 20 dígitos (se permite + al inicio)")
    if correo and (len(correo) > 120 or not _RE_CORREO.match(correo)):
        error("correo", "no tiene un formato válido (ej. nombre@dominio.com)")

    if errores:
        resumen = "; ".join(f"{e['campo']}: {e['mensaje']}" for e in errores)
        raise EntradaInvalidaError(f"Datos de entrada inválidos. {resumen}", errores=errores)
    return NuevoHuesped(nombre, documento, nacionalidad, telefono, correo)


def _id_valido(id_huesped: int) -> None:
    if not isinstance(id_huesped, int) or id_huesped <= 0:
        raise EntradaInvalidaError("El id del huésped debe ser un entero positivo.", campo="id_huesped")


class GestionHuespedesService:
    def __init__(self, proveedor: ProveedorRepositorios):
        self._p = proveedor

    # ---------------------------------------------------------------- lectura
    def listar(self, buscar: str | None = None) -> list[Huesped]:
        texto = _limpio(buscar)
        if texto and len(texto) > 60:
            raise EntradaInvalidaError("El texto de búsqueda es demasiado largo (máx. 60).", campo="buscar")
        return self._p.leer(lambda r: r.huespedes.listar(texto))

    def obtener(self, id_huesped: int) -> Huesped:
        _id_valido(id_huesped)
        h = self._p.leer(lambda r: r.huespedes.obtener_por_id(id_huesped))
        if h is None:
            raise NoEncontradoError(MSG_NO_EXISTE)
        return h

    def obtener_por_correo(self, correo: str) -> Huesped | None:
        """Para el rol huésped: su ficha es la que tiene el mismo correo de su cuenta."""
        correo = (correo or "").strip().lower()
        if not correo:
            return None
        return next((h for h in self._p.leer(lambda r: r.huespedes.listar(correo))
                     if (h.correo or "").lower() == correo), None)

    # ---------------------------------------------------------------- escritura
    def crear(self, datos: DatosHuesped) -> Huesped:
        nuevo = validar(datos)

        def caso(r):
            id_nuevo = r.huespedes.crear(nuevo)
            return r.huespedes.obtener_por_id(id_nuevo)  # se responde con lo que quedó guardado

        return self._escribir(caso)

    def actualizar(self, id_huesped: int, datos: DatosHuesped) -> Huesped:
        _id_valido(id_huesped)
        nuevo = validar(datos)

        def caso(r):
            if not r.huespedes.actualizar(id_huesped, nuevo):
                raise NoEncontradoError(MSG_NO_EXISTE)
            return r.huespedes.obtener_por_id(id_huesped)

        return self._escribir(caso)

    def eliminar(self, id_huesped: int) -> None:
        _id_valido(id_huesped)

        def caso(r):
            if r.huespedes.obtener_por_id(id_huesped) is None:
                raise NoEncontradoError(MSG_NO_EXISTE)
            activas = r.huespedes.contar_reservas_activas(id_huesped)
            if activas:
                raise HuespedConReservasError(MSG_CON_RESERVAS.format(n=activas))
            r.huespedes.eliminar(id_huesped)

        self._escribir(caso)

    def _escribir(self, caso):
        try:
            return self._p.escribir(caso)
        except DuplicadoError as e:
            raise DatoDuplicadoError(MSG_DUPLICADO.get(e.campo, "Dato repetido."), campo=e.campo) from e
        except DatosRechazadosPorBD as e:
            raise EntradaInvalidaError("La base de datos rechazó los datos del huésped.") from e
