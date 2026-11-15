# Marea Dorada Resort

Aplicación web de gestión hotelera con React + Vite en el frontend y FastAPI + MongoDB en el backend.

## Instalación rápida (Windows)

1. Copia `.env.example` como `.env` y configura la conexión a MongoDB y `SECRET_KEY`.
2. Crea y activa el entorno virtual:

## Semana 13 — Persistencia del corte vertical

Requiere MongoDB en modo **replica set** (`rs0`) para las transacciones; los pasos están en la sección 4 de README_SEMANA13.md.
Ver [README_SEMANA13.md](README_SEMANA13.md): matriz RF–RNF, esquema MongoDB (validadores e índices), datos de prueba, repositorios, pruebas y evidencias.

## Semana 14 — Lógica de negocio y API del corte

Ver [README_SEMANA14.md](README_SEMANA14.md): servicios de RF-02 y RF-04, contratos de la API (`/api/disponibilidad`, `/api/reservas`), pruebas funcionales, matriz RF–RNF con evidencias y relevo a la interfaz.

Arranque rápido de la API del corte: `uvicorn app.api.app:app --reload --port 8000` y abrir http://127.0.0.1:8000/docs
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