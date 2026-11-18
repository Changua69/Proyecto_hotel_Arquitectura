"""Permisos por rol para las rutas /api (semana 15).

El token es el mismo JWT que entrega POST /login (campos "sub" = correo y "role").
Roles: "huesped" (por defecto al registrarse), "recepcionista" y "admin".

    @router.get(..., dependencies=[Depends(requiere_rol("recepcionista", "admin"))])
    def endpoint(usuario: Usuario = Depends(requiere_rol(...))): ...

- Sin token o token vencido -> 401 NO_AUTENTICADO.
- Rol no permitido         -> 403 SIN_PERMISO.
El permiso se decide en el BACKEND: ocultar botones en la pantalla no basta.
"""
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.errores import NoAutenticadoError, SinPermisoError

ROLES_PERSONAL = ("recepcionista", "admin")
_bearer = HTTPBearer(auto_error=False, description="Token de POST /login")


@dataclass(frozen=True)
class Usuario:
    correo: str
    rol: str

    @property
    def es_personal(self) -> bool:
        return self.rol in ROLES_PERSONAL


def usuario_actual(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Usuario:
    if cred is None or not cred.credentials:
        raise NoAutenticadoError("Debe iniciar sesión para usar esta función.")
    # Import diferido: jwt_handler exige SECRET_KEY al importarse.
    from app.auth.jwt_handler import verify_token

    datos = verify_token(cred.credentials)
    if not datos:
        raise NoAutenticadoError("La sesión no es válida o venció. Inicie sesión de nuevo.")
    return Usuario(correo=str(datos["sub"]).lower(), rol=str(datos.get("role") or "huesped"))


def requiere_rol(*roles: str):
    def dependencia(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise SinPermisoError("Su rol no tiene permiso para esta operación.")
        return usuario

    return dependencia
