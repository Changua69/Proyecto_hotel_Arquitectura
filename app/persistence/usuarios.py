"""Repositorio de cuentas de acceso (semana 15, módulo de Administración).

Las cuentas viven en la colección `users` de la base de la aplicación (DATABASE_NAME, por defecto
hotel_db), la misma que usan /register y /login. Este repositorio es el único acceso a esa colección
desde el módulo de Administración. Nunca devuelve la contraseña (solo se guarda su hash bcrypt).
"""
from pymongo.errors import DuplicateKeyError

from app.persistence.errors import BaseNoDisponibleError, DuplicadoError
from app.persistence.models import Usuario


def _coleccion():
    from app.database import users_collection

    return users_collection


def _a_modelo(d: dict) -> Usuario:
    return Usuario(email=d["email"], nombre=d.get("name") or "", rol=d.get("role") or "huesped")


class MongoUsuarioRepository:
    def __init__(self, coleccion=None):
        self._c = coleccion if coleccion is not None else _coleccion()

    def _ejecutar(self, fn):
        from pymongo.errors import ConnectionFailure

        try:
            return fn()
        except ConnectionFailure as e:
            raise BaseNoDisponibleError("No hay conexión con la base de usuarios") from e

    def listar(self) -> list[Usuario]:
        return self._ejecutar(lambda: [_a_modelo(d) for d in self._c.find({}, {"password": 0}).sort("email", 1)])

    def obtener(self, email: str) -> Usuario | None:
        d = self._ejecutar(lambda: self._c.find_one({"email": email}, {"password": 0}))
        return _a_modelo(d) if d else None

    def crear(self, usuario: Usuario, hash_clave: str) -> None:
        def insertar():
            try:
                self._c.insert_one({"email": usuario.email, "name": usuario.nombre, "role": usuario.rol,
                                    "password": hash_clave})
            except DuplicateKeyError as e:
                raise DuplicadoError("email") from e

        self._ejecutar(insertar)

    def cambiar_rol(self, email: str, rol: str) -> bool:
        return self._ejecutar(lambda: self._c.update_one({"email": email}, {"$set": {"role": rol}}).matched_count == 1)

    def eliminar(self, email: str) -> bool:
        return self._ejecutar(lambda: self._c.delete_one({"email": email}).deleted_count == 1)

    def contar_rol(self, rol: str) -> int:
        return self._ejecutar(lambda: self._c.count_documents({"role": rol}))
