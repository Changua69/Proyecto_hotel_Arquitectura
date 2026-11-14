- Installar mongodb shell

- Agragar la carpeta bin de mongo en el path ("C:\Program Files\MongoDB\Server\8.0\bin")

- pip install instaladores.txt
  
- Con el cmd cambiar la ruta a donde esta el proyecto y despues activar el entorno virtual "venv\Scripts\activate" y para iniciar el servidor es con "uvicorn app.main:app --reload"




## Semana 13 — Persistencia del corte vertical

Requiere MongoDB en modo **replica set** (`rs0`) para las transacciones; los pasos están en la sección 4 de README_SEMANA13.md.
Ver [README_SEMANA13.md](README_SEMANA13.md): matriz RF–RNF, esquema MongoDB (validadores e índices), datos de prueba, repositorios, pruebas y evidencias.

## Semana 14 — Lógica de negocio y API del corte

Ver [README_SEMANA14.md](README_SEMANA14.md): servicios de RF-02 y RF-04, contratos de la API (`/api/disponibilidad`, `/api/reservas`), pruebas funcionales, matriz RF–RNF con evidencias y relevo a la interfaz.

Arranque rápido de la API del corte: `uvicorn app.api.app:app --reload --port 8000` y abrir http://127.0.0.1:8000/docs
