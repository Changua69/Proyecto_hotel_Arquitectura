import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, rooms, reservations, dashboard
from app.init_rooms import init_rooms
from app.api.app import registrar_corte
from app.database import client

load_dotenv()

app = FastAPI(title="Marea Dorada Resort API")

# En producción configura CORS_ORIGINS con la URL exacta de Vercel.
# En local se permiten también los orígenes habituales de Vite.
origins_configured = os.getenv("CORS_ORIGINS", "")
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in origins_configured.split(",")
    if origin.strip()
]
allowed_origins.extend([
    "http://localhost:5173",
    "http://127.0.0.1:5173",
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(allowed_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Location", "Content-Disposition"],  # semana 15: id creado y nombre del PDF
)

app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(reservations.router)
app.include_router(dashboard.router)
registrar_corte(app)  # semana 14: /api/disponibilidad, /api/reservas; semana 15: huéspedes, panel, admin, reportes


@app.get("/")
def root():
    return {"message": "API del hotel funcionando"}


@app.get("/health")
def health():
    """Endpoint para comprobar que la API y MongoDB están disponibles."""
    client.admin.command("ping")
    return {"status": "ok", "database": "connected"}


@app.on_event("startup")
def startup_event():
    # Es seguro ejecutarlo al iniciar: solo crea habitaciones faltantes.
    init_rooms()
    auth.asegurar_email_unico()  # no se repiten correos de usuarios
    # Semana 15: la base del corte queda lista (tipos y habitaciones) aunque nadie haya corrido
    # reset_db en producción. No destructivo: no borra nada ni carga datos de prueba.
    try:
        from scripts.preparar_base import preparar

        cambios = preparar(verbose=False)
        if cambios:
            print("[startup] base del corte preparada:", "; ".join(cambios))
    except Exception as e:  # la API sigue arrancando; /api responderá 503 si la base no está disponible
        print(f"[startup] no se pudo preparar la base del corte: {type(e).__name__}: {e}")

