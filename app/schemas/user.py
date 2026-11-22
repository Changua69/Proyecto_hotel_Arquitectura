from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: str
    # Semana 15: al registrarse también se crea la ficha del huésped (mismo correo).
    # Opcional solo si recepción ya había registrado una ficha con ese correo.
    documento: str | None = None
    nacionalidad: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str