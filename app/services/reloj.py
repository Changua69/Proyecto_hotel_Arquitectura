"""Fecha de "hoy" del hotel (semana 15).

El servidor de producción (Render) corre en UTC: a las 7 p. m. de Colombia allá ya es el día
siguiente, y reglas como "la entrada no puede ser anterior a hoy" fallaban de noche. Todas las reglas
de negocio usan esta función, con la zona horaria del hotel (por defecto America/Bogota; se puede
cambiar con la variable de entorno ZONA_HORARIA_HOTEL).
"""
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONA_HOTEL = ZoneInfo(os.getenv("ZONA_HORARIA_HOTEL", "America/Bogota"))


def hoy_hotel() -> date:
    return datetime.now(ZONA_HOTEL).date()
