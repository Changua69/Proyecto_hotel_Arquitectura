"""Crear o actualizar usuarios con rol (semana 15).

El registro público (POST /register) siempre crea cuentas con rol "huesped". Las cuentas del
personal (recepcionista, admin) se crean con este script, directamente en la base de usuarios.

Uso (desde la raíz del proyecto, con el entorno virtual activo):
    python -m scripts.crear_usuario --email recepcion@marea.test --rol recepcionista --nombre "Recepción"
        -> pide la contraseña sin mostrarla en pantalla
    python -m scripts.crear_usuario --demo
        -> crea las 3 cuentas de demostración de la tabla de abajo (solo en una base LOCAL)

Cuentas de demostración (contraseña Demo1234, NO son credenciales reales):
    admin@marea.test      admin
    recepcion@marea.test  recepcionista
    ana@example.com       huesped   (mismo correo de la huésped 1 de los datos de prueba)

Si el correo ya existe, se actualizan el rol, el nombre y la contraseña.
"""
import argparse
import getpass
import os
import sys

ROLES = ("huesped", "recepcionista", "admin")
CLAVE_DEMO = "Demo1234"
DEMO = [
    ("admin@marea.test", "admin", "Administración"),
    ("recepcion@marea.test", "recepcionista", "Recepción"),
    ("ana@example.com", "huesped", "Ana Torres"),
]


def guardar(email: str, rol: str, nombre: str, clave: str) -> str:
    from passlib.context import CryptContext

    from app.database import users_collection
    from app.routes.auth import SIN_MAYUSCULAS, normalizar_email

    email = normalizar_email(email)
    hash_ = CryptContext(schemes=["bcrypt"], deprecated="auto").hash(clave)
    r = users_collection.update_one(
        {"email": email},
        {"$set": {"email": email, "role": rol, "name": nombre, "password": hash_}},
        upsert=True,
        collation=SIN_MAYUSCULAS,
    )
    return "creado" if r.upserted_id else "actualizado"


def main() -> None:
    ap = argparse.ArgumentParser(description="Crear usuarios con rol")
    ap.add_argument("--email")
    ap.add_argument("--rol", choices=ROLES)
    ap.add_argument("--nombre", default="")
    ap.add_argument("--demo", action="store_true", help="Crear las cuentas de demostración (base local)")
    ap.add_argument("--forzar", action="store_true", help="Permitir --demo en una base remota (no recomendado)")
    a = ap.parse_args()

    if a.demo:
        uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
        if uri.startswith("mongodb+srv://") and not a.forzar:
            sys.exit("La base parece remota (Atlas). Las cuentas demo tienen una contraseña conocida; "
                     "cree cuentas reales sin --demo, o use --forzar si es una base de prueba.")
        for email, rol, nombre in DEMO:
            print(f"{guardar(email, rol, nombre, CLAVE_DEMO):<11} {email:<22} {rol}")
        print(f"\nContraseña de las cuentas demo: {CLAVE_DEMO}")
        return

    if not a.email or not a.rol:
        ap.error("use --email y --rol, o --demo")
    clave = getpass.getpass("Contraseña: ")
    if len(clave) < 8:
        sys.exit("La contraseña debe tener al menos 8 caracteres.")
    if clave != getpass.getpass("Repita la contraseña: "):
        sys.exit("Las contraseñas no coinciden.")
    print(f"Usuario {guardar(a.email, a.rol, a.nombre or a.email, clave)}: {a.email} ({a.rol})")


if __name__ == "__main__":
    main()
