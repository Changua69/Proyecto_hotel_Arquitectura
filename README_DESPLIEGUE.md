# Despliegue de Marea Dorada Resort

Esta configuración utiliza:
- **Frontend:** Vercel (React + Vite).
- **Backend:** Render (FastAPI + Uvicorn).
- **Base de datos:** MongoDB Atlas.

## 1. Configurar MongoDB Atlas

1. Crea un cluster en MongoDB Atlas.
2. Crea un usuario de base de datos con contraseña segura.
3. En Network Access autoriza las conexiones del backend. En Render Free la IP de salida puede cambiar; si utilizas `0.0.0.0/0`, usa una contraseña fuerte y un usuario con permisos mínimos sobre la base `hotel_db`.
4. Copia la cadena de conexión (`mongodb+srv://...`) y reemplaza usuario, contraseña y nombre de cluster.
5. No publiques la cadena de conexión ni la guardes en GitHub.

## 2. Desplegar FastAPI en Render

El repositorio incluye `render.yaml` para facilitar el despliegue.

1. Sube los cambios del proyecto a GitHub.
2. Entra a https://render.com y crea un **New + > Blueprint** (o un Web Service conectado al repositorio).
3. Si usas Blueprint, Render leerá `render.yaml`. Si creas el Web Service manualmente, utiliza:
   - Root Directory: la raíz del repositorio (donde están `app/` y `requirements.txt`).
   - Runtime: Python 3.
   - Build Command: `pip install -r requirements.txt`.
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
   - Health Check Path: `/health`.
4. Configura estas variables de entorno en Render:
   - `MONGO_URI`: cadena de conexión de MongoDB Atlas.
   - `DATABASE_NAME`: `hotel_db`.
   - `SECRET_KEY`: una clave aleatoria larga y privada. Puedes generarla con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   - `CORS_ORIGINS`: URL pública exacta de Vercel, por ejemplo `https://tu-proyecto.vercel.app`, sin barra final.
5. Espera a que termine el despliegue.
6. Abre `https://TU-BACKEND.onrender.com/health`. Debe responder `{"status":"ok","database":"connected"}`.
7. Abre `https://TU-BACKEND.onrender.com/docs` para comprobar Swagger.

Render Free puede suspender el servicio cuando no recibe solicitudes; la primera petición posterior puede tardar en responder.

## 3. Desplegar React en Vercel

1. Importa el mismo repositorio en Vercel.
2. En **Root Directory** selecciona `frontend`.
3. Framework Preset: `Vite`.
4. Build Command: `npm run build`.
5. Output Directory: `dist`.
6. En **Settings > Environment Variables**, agrega:
   - Name: `VITE_API_URL`
   - Value: `https://TU-BACKEND.onrender.com` (sin barra final).
   - Environment: Production (y Preview si también quieres probar previews).
7. Guarda y ejecuta un nuevo Deploy.

El archivo `frontend/vercel.json` permite que las rutas de React Router funcionen al recargar una página.

## 4. Desarrollo local

En la raíz del proyecto copia `.env.example` como `.env` y configura `MONGO_URI`, `DATABASE_NAME` y `SECRET_KEY`. Para MongoDB local, el valor de ejemplo es `mongodb://127.0.0.1:27017`.

En una terminal:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

En `frontend`, crea `.env` a partir de `.env.example` y ejecuta:

```bash
npm install
npm run dev
```

## 5. Importante sobre datos existentes

La inicialización de habitaciones ya no elimina la colección. Al iniciar, solo crea las habitaciones que falten y conserva los datos existentes. Sin embargo, una base de datos nueva en Atlas estará vacía de usuarios y reservas: los datos que existan únicamente en MongoDB local no se copian automáticamente. Si necesitas conservarlos, exporta e importa la base de datos antes de cambiar la conexión.

## 6. Seguridad

- No subas `.env` a GitHub. Está excluido mediante `.gitignore`.
- Si alguna credencial real ya se subió a un repositorio público, cámbiala en MongoDB Atlas y genera una nueva `SECRET_KEY`.
- No uses `allow_origins=["*"]` junto con credenciales en producción; configura `CORS_ORIGINS` con el dominio exacto de Vercel.
- `VITE_API_URL` es una variable pública del frontend. Nunca pongas contraseñas, URI de MongoDB ni claves JWT en variables `VITE_`.
