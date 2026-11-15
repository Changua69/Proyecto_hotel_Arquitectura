import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.collation import Collation
from pymongo.errors import DuplicateKeyError, OperationFailure
from app.database import users_collection
from app.schemas.user import UserRegister
from app.auth.jwt_handler import create_access_token
from passlib.context import CryptContext

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
log = logging.getLogger("marea.auth")

# Compara correos sin distinguir mayúsculas de minúsculas: "Ana@Correo.com" == "ana@correo.com".
SIN_MAYUSCULAS = Collation(locale="en", strength=2)
MSG_CORREO_REPETIDO = "Ya existe una cuenta con ese correo."


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def asegurar_email_unico() -> None:
    """Índice único (sin distinguir mayúsculas) sobre el correo de los usuarios.
    Impide correos repetidos incluso si dos registros llegan al mismo tiempo.
    Si la base ya tiene correos repetidos de antes, no se puede crear: se avisa en el
    log y la verificación del registro sigue funcionando."""
    try:
        users_collection.create_index("email", unique=True, collation=SIN_MAYUSCULAS, name="ux_usuario_email")
    except OperationFailure as e:
        log.warning("No se pudo crear el índice único de correos (¿hay correos repetidos en la base?): %s", e)


@router.post("/register", status_code=201)
def register(user: UserRegister):

    email = normalizar_email(user.email)

    existing_user = users_collection.find_one({"email": email}, collation=SIN_MAYUSCULAS)

    if existing_user:
        raise HTTPException(status_code=409, detail=MSG_CORREO_REPETIDO)

    hashed_password = pwd_context.hash(user.password)

    user_dict = {
        "name": user.name,
        "email": email,
        "password": hashed_password,
        "phone": user.phone,
        "role": "huesped"
    }

    try:
        users_collection.insert_one(user_dict)
    except DuplicateKeyError:
        # Otro registro con el mismo correo se guardó justo antes que este.
        raise HTTPException(status_code=409, detail=MSG_CORREO_REPETIDO)

    return {"message": f"Bienvenido {user.name} al Marea Dorada Resort"}


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):

    existing_user = users_collection.find_one(
        {"email": normalizar_email(form_data.username)}, collation=SIN_MAYUSCULAS
    )

    if not existing_user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    if not pwd_context.verify(form_data.password, existing_user["password"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = create_access_token({
        "sub": existing_user["email"],
        "role": existing_user["role"]
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": existing_user["role"]
    }
