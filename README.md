# Marea Dorada Resort

Aplicación web de gestión hotelera con React + Vite en el frontend y FastAPI + MongoDB en el backend.

## Instalación rápida (Windows)

1. Copia `.env.example` como `.env` y configura la conexión a MongoDB y `SECRET_KEY`.
2. Crea y activa el entorno virtual:

```bash
python -m venv venv
venv\Scripts\activate
```

3. Instala las dependencias:

```bash
pip install -r requirements.txt
```

4. Inicia el backend:

```bash
uvicorn app.main:app --reload
```

5. En otra terminal, entra a `frontend`, copia `.env.example` como `.env`, instala dependencias e inicia Vite:

```bash
cd frontend
npm install
npm run dev
```

## Despliegue

Consulta [README_DESPLIEGUE.md](README_DESPLIEGUE.md) para desplegar React en Vercel, FastAPI en Render y MongoDB en Atlas.

## Semana 13 — Persistencia

Consulta [README_SEMANA13.md](README_SEMANA13.md) para la documentación del corte vertical de persistencia, pruebas y evidencias.
