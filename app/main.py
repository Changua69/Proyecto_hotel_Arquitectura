from fastapi import FastAPI
from app.routes import auth, rooms, reservations, dashboard
from app.init_rooms import init_rooms
from fastapi.middleware.cors import CORSMiddleware
from app.api.app import registrar_corte

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en desarrollo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(reservations.router)
app.include_router(dashboard.router)
registrar_corte(app)  # semana 14: /api/disponibilidad, /api/reservas


@app.get("/")
def root():
    return {"message": "API del hotel funcionando"}

@app.on_event("startup")
def startup_event():
    init_rooms()
    auth.asegurar_email_unico()  # no se repiten correos de usuarios