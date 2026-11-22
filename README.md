# MareaDorada Pro v1.0 — Marea Dorada Resort

Aplicación web de gestión hotelera. Corte vertical de punta a punta:
**Interfaz (React) → API (FastAPI) → Servicio → Repositorio → Base de datos (MongoDB)**.

Arquitectura de Sistemas I · Universidad Central · Docente: Ing. Elías Buitrago Bolívar

## Integrantes

- Erick Genaldo Flores
- Juan David Arroyave

## Los 2 RF priorizados del corte

| Prioridad | RF | Qué hace | Endpoint | Pantalla |
|---|---|---|---|---|
| 1 | **RF-04 Crear reserva** | Asigna la habitación libre de menor número del tipo pedido, calcula el total y guarda la reserva CONFIRMADA. Responde 201 solo después de guardar. | `POST /api/reservas` (+ `GET /api/reservas/{id}` para confirmar) | Panel → **Nueva reserva** |
| 2 | **RF-02 Consultar disponibilidad** | Lista las habitaciones del tipo sin reservas activas que se crucen con las fechas. | `GET /api/disponibilidad` | Panel → **Nueva reserva** |

Extras de la semana 15 (fuera de los 2 RF priorizados): dashboard general, CRUD de huéspedes,
permisos por rol, listado y cancelación de reservas, módulo de administración (usuarios, roles y
tarifas) y reporte de ventas en PDF.

---

## 1. Configuración (sin credenciales reales)

Copie los archivos de ejemplo y ajuste los valores. **Los `.env` no se suben a GitHub** (están en
`.gitignore`). La cadena de MongoDB Atlas (`mongodb+srv://...`) solo va en el `.env` local o en las
variables de Render, nunca en el repositorio ni en el chat.

`.env` (raíz del proyecto, a partir de `.env.example`):

```env
MONGO_URI=mongodb://127.0.0.1:27017/?replicaSet=rs0   # replica set: necesario para transacciones
MONGO_DB_PRUEBA=marea_test                            # base del corte (reset_db la borra y recrea)
DATABASE_NAME=hotel_db                                # cuentas de usuario (login)
SECRET_KEY=cambiar_esta_clave                         # firma de los tokens: use un valor largo y aleatorio
# CORS_ORIGINS=https://su-frontend.vercel.app         # solo en producción
```

`frontend/.env` (a partir de `frontend/.env.example`):

```env
VITE_API_URL=http://127.0.0.1:8000
```

## 2. Puertos y URL

| Componente | Local | Producción |
|---|---|---|
| Frontend (Vite) | http://localhost:5173 | https://proyecto-hotel-arquitectura-lovat.vercel.app/ |
| Backend (FastAPI) | http://127.0.0.1:8000 · documentación: http://127.0.0.1:8000/docs | Servicio de Render (variable `VITE_API_URL` del frontend en Vercel) |
| MongoDB | 127.0.0.1:27017, replica set `rs0` | MongoDB Atlas |

## 3. Comandos de arranque

Requisitos: Python 3.12+, Node 20+, MongoDB 8 en replica set (o Docker).

```bash
# 0) MongoDB en replica set (opción Docker; detenga antes un MongoDB local en el puerto 27017)
docker compose up -d

# 1) Backend (terminal 1)
python -m venv venv
venv\Scripts\activate                       # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt -r requirements-corte.txt
python -m scripts.reset_db                  # datos iniciales del corte
python -m scripts.crear_usuario --demo      # cuentas de demostración (solo base local)
uvicorn app.main:app --reload --port 8000

# 2) Frontend (terminal 2)
cd frontend
npm install
npm run dev                                 # http://localhost:5173
```

En PowerShell, si no deja activar el entorno: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## 4. Datos iniciales

`python -m scripts.reset_db` deja siempre el mismo estado (base `marea_test`):

- **Tipos:** 1 Estándar (cap. 2, $120.000/noche) · 2 Familiar (cap. 4, $200.000) · 3 Suite (cap. 3, $280.000).
- **24 habitaciones:** Estándar 101–112, Familiar 201–208, Suite 301–304.
- **Huéspedes:** 1 Ana Torres (ana@example.com) · 2 Carlos Méndez · 3 Laura Smith.
- **Reservas:** 1) Suite 301, 20–23 dic 2026, CONFIRMADA · 2) Suite 302, mismas fechas, CANCELADA ·
  3) Estándar 101, 10–12 dic 2026, CONFIRMADA. El próximo id de reserva es 4 y el de huésped, 4.

Cuentas de demostración (`scripts.crear_usuario --demo`, contraseña `Demo1234`; **no son credenciales
reales** y el script se niega a crearlas en Atlas):

| Correo | Rol | Qué puede hacer |
|---|---|---|
| admin@marea.test | admin | Todo, incluido Administración, eliminar huéspedes y reporte PDF |
| recepcion@marea.test | recepcionista | Dashboard, Nueva reserva, Huéspedes (sin eliminar), Reservas |
| ana@example.com | huesped | Portal del huésped y **Mis reservas** (solo ve las suyas) |

Para cuentas reales del personal: `python -m scripts.crear_usuario --email ... --rol recepcionista`
(pide la contraseña sin mostrarla).

## 5. Pasos para repetir la prueba

**Automática (backend y base):**

```bash
python -m pytest -v            # 120 pruebas: aisladas (sin base) + contra MongoDB real
python -m scripts.verificar_capas
```

**De extremo a extremo desde la pantalla** (con backend y frontend encendidos; navegador una sola vez:
`pip install playwright && python -m playwright install chromium`):

```bash
python -m scripts.e2e_pantalla         # agregue --ver para ver el navegador
```

Recorre CA-01 a CA-07, el tiempo visto por el usuario (RNF-01), 10 pantallas confirmando a la vez la
última Suite (RNF-08), el 404 que oculta datos anteriores y la caída del backend. Guarda
`evidencias/semana15/e2e_pantalla.json` y capturas en `evidencias/semana15/capturas/`.

**Manual (demostración en vivo):**

1. `python -m scripts.reset_db` e iniciar sesión como **recepcion@marea.test**.
2. **Nueva reserva:** huésped #1, Familiar, 20 → 23 dic 2026, 3 personas → *Consultar disponibilidad*
   (201–208) → *Confirmar reserva* → **“Reserva #4 confirmada”**, habitación 201, $600.000.
3. Abajo, *Consultar una reserva por ID*: `4` → “ID confirmado”; `999` → “La reserva no existe” (desaparece lo anterior).
4. Cambiar a Suite, 3 → 9 personas → “El tipo Suite admite como máximo 3 personas” (422).
5. **Huéspedes:** *+ Nuevo huésped* con documento `1020304050` → “Ya existe un huésped con ese
   documento” (409) con el campo marcado y los datos conservados; corregir → “Huésped #4 registrado”.
   Probar cerrar la ventana con Esc, con la X y con clic fuera.
6. Apagar el backend y guardar algo → “No se pudo conectar con el servidor…” (sin falso éxito).
7. Entrar como **admin@marea.test** → **Administración** → *Reporte de ventas* (1–31 dic 2026) →
   *Descargar PDF*.

---

## 6. Endpoints de la semana 15

| Método y ruta | Quién | Respuestas |
|---|---|---|
| `GET /api/disponibilidad` | Público | 200, 400, 404, 422, 503 |
| `POST /api/reservas` · `GET /api/reservas/{id}` | Personal: cualquier huésped · Huésped: solo para sí | 201/200, 400, 401, 403, 404, 409, 422, 503 |
| `GET /api/reservas?estado&desde&hasta` | Personal: todas · Huésped: las suyas | 200, 400, 401 |
| `POST /api/reservas/{id}/cancelar` | recepcionista, admin | 204, 401, 403, 404, 409 |
| `GET/POST /api/huespedes`, `GET/PUT /api/huespedes/{id}` | recepcionista, admin (el huésped solo ve su ficha y `/api/huespedes/yo`) | 200/201, 400, 401, 403, 404, 409 |
| `DELETE /api/huespedes/{id}` | admin (409 si tiene reservas activas) | 204, 403, 404, 409 |
| `GET /api/panel/resumen` | recepcionista, admin | 200, 401, 403 |
| `GET /api/reportes/ventas` · `GET /api/reportes/ventas.pdf` | admin | 200 (JSON / `application/pdf`), 400, 403 |
| `/api/admin/usuarios…` · `/api/admin/tipos…` | admin (consultar tipos: personal) | 200/201/204, 400, 403, 404, 409 |

Formato de error de todas las rutas `/api`: `{"detail": "...", "codigo": "..."}`, más `"campo"` o
`"errores": [{"campo", "mensaje"}]` cuando hay que marcar un campo del formulario. Fechas siempre
`AAAA-MM-DD`.

## 7. Estructura

```text
app/
  api/            # HTTP: rutas, esquemas JSON, permisos por rol (seguridad.py), errores, PDF
  services/       # reglas de negocio (reservas, huéspedes, panel, administración, reporte)
  persistence/    # único acceso a MongoDB: repositorios, transacciones, modelos
  routes/ auth/   # login y registro (heredados)
db/               # esquema (validadores e índices) y datos de prueba
scripts/          # reset_db, crear_usuario, verificar_capas, e2e_pantalla, mediciones
tests/            # pytest (aisladas y contra MongoDB real)
frontend/src/
  components/     # Modal, ConfirmDialog, StaffLayout, RequireRole
  pages/          # Login, Panel, NuevaReserva, Huespedes, Reservas, Administracion, portal del huésped
  services/       # api.ts (token y clasificación de errores), contratos por módulo
  hooks/          # useCarga (estados en curso / resultado / error)
evidencias/       # semana13, semana14, semana15
```

---

## 8. Matriz de cierre RF–RNF

Conserva los identificadores y metas de las semanas 13 y 14 y agrega la verificación de extremo a
extremo de la semana 15. **Estados posibles:** Cumple · Cumple parcialmente · No cumple · Pendiente.

| RF | RNF | Característica ISO/IEC 25010:2023 | Escenario y meta | Sem. 13 (persistencia) | Sem. 14 (servicio y API) | Sem. 15 (extremo a extremo, desde la pantalla) | Resultado observado | Estado | Riesgo residual / acción |
|---|---|---|---|---|---|---|---|---|---|
| RF-02, RF-04 | **RNF-01** | Eficiencia de desempeño / comportamiento temporal | 10 usuarios concurrentes; p95 ≤ 2 000 ms y todas 200 | `rnf01_tiempos.json` (repositorio) | `rnf01_api.json`: p95 38 ms por HTTP | `e2e_pantalla.json` → RNF-01: tiempo visto por el usuario, 10 consultas y 10 creaciones | Local: consulta p95 82 ms, creación p95 79 ms | **Cumple** (local) | En Render Free el primer acceso tras inactividad tarda (arranque en frío); se mide aparte con `medir_latencia_produccion.py` |
| RF-04 | **RNF-03** | Fiabilidad / tolerancia a fallos | Fallo después de guardar y antes de confirmar: 0 documentos parciales | `test_integridad_*` | `test_rnf03_*`: 500 genérico, contador sin avanzar | Escenario “Caída”: la pantalla avisa “No se pudo conectar…”, no muestra “confirmada” y conserva los datos | Sin datos parciales ni falsos éxitos | **Cumple** | Si la red cae justo después de guardar, la pantalla pide revisar *Reservas* antes de repetir |
| RF-02, RF-04 | **RNF-06** | Mantenibilidad / modularidad y capacidad para ser probado | Servicios probados sin base; 0 accesos a MongoDB fuera de `app/persistence` | Repositorios separados | 20 pruebas aisladas | + 9 pruebas aisladas del servicio de huéspedes; `verificar_capas.txt`: 0 hallazgos | 120 pruebas en verde | **Cumple** | Las rutas heredadas (login, portal) aún acceden directo a MongoDB; están fuera del corte |
| RF-04 | **RNF-08** | Fiabilidad / ausencia de fallos | 10 solicitudes simultáneas por la única Suite libre: 1 reserva y 9 rechazos | Índice único parcial (habitación, noche) | `test_rnf08_*` por API: 1×201, 9×409 | CA-07: 10 pantallas confirman a la vez: 1 “confirmada”, 9 “Ya no hay habitaciones” | 1 sola reserva activa en la 304 | **Cumple** | — |
| RF-04 | Seguridad (complementario) | Seguridad / confidencialidad y autenticidad | Solo el personal crea reservas para otros; el huésped solo ve lo suyo | — | — | `test_api_huespedes.py`: 401 sin sesión, 403 por rol, huésped limitado a su ficha y reservas | Permisos aplicados en el backend | **Cumple** | Tokens de 60 min en `localStorage`; usar HTTPS en producción (Vercel/Render lo dan) |
| RF-02, RF-04 | Usabilidad (complementario) | Interacción / protección contra errores del usuario | Estados en curso, resultado y error; sin dobles envíos; sin datos viejos tras un error | — | Contratos con `codigo` y `errores[].campo` | CA-03b, CA-05, CA-06 y 404 desde la pantalla; capturas en `evidencias/semana15/capturas/` | Mensajes claros y campos marcados | **Cumple** | — |

**Criterios de aceptación recorridos desde la pantalla (`e2e_pantalla.json`):**

| CA | Escenario | Resultado |
|---|---|---|
| CA-01 | Familiar, 3 personas, 20–23 dic | “Reserva #4 confirmada”, hab. 201, $600.000; ID confirmado |
| CA-02 | Suites 21–22 dic | 302, 303, 304 (la 301 ocupada no aparece; la 302 cancelada no bloquea) |
| CA-03 | Sin disponibilidad | Aviso y botón Confirmar deshabilitado; si otro usuario toma la última antes de confirmar: 409 claro, sin reserva nueva |
| CA-04 | Rango contiguo (entra el día que otro sale) | Permitido, asigna la 301 |
| CA-05 | Capacidad excedida | “El tipo Estándar admite como máximo 2 personas.” |
| CA-06 | Fechas inválidas | Campo marcado y envío bloqueado (el backend además responde 400) |
| CA-07 | 10 usuarios por la última Suite | 1 confirmada, 9 rechazadas, 1 reserva activa |

Documentación de semanas anteriores: [README_SEMANA13.md](README_SEMANA13.md) (persistencia) ·
[README_SEMANA14.md](README_SEMANA14.md) (servicios y API) · [README_DESPLIEGUE.md](README_DESPLIEGUE.md)
(Vercel + Render + Atlas).
