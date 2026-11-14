# MareaDorada Pro v1.0 — Semana 14: lógica de negocio y API del corte vertical

**Arquitectura de Sistemas I** · Docente: Ing. Elías Buitrago Bolivar
**Integrantes:** Erick Genaldo Flores · Juan David Arroyave

La semana 14 del curso es la **etapa 2** del prototipo; las guías la llaman “semana 2”. Sobre la
persistencia probada en la semana 13 (`README_SEMANA13.md`), los dos RF priorizados ya **funcionan por
API**: tienen servicios con las reglas RN-01 a RN-05, contratos documentados, pruebas funcionales con
MongoDB real y los RNF verificados hasta donde lo permite la API.

**Resultado:** 69 pruebas pasan: 15 de persistencia, 29 funcionales por API contra MongoDB real,
20 aisladas sin base de datos (17 de servicios y 3 de errores y CORS) y 5 de correos únicos (sección 8). RNF-01 medido por HTTP con 10 usuarios concurrentes: **p95 = 38 ms**,
con una meta de 2 000 ms.

```
API (app/api)  →  Servicios (app/services)  →  Repositorios (app/persistence)  →  MongoDB
  HTTP ↔ JSON       reglas RN-01 a RN-05          consultan y guardan              replica set rs0
```

---

## 1. Los dos RF: servicios y reglas

Se conservan los identificadores, la prioridad y el alcance de la semana 13.

| Prioridad | RF | Servicio | Entrada | Reglas y condiciones | Métodos de repositorio | Resultado válido | Rechazos |
|---|---|---|---|---|---|---|---|
| **1** | **RF-04 Crear reserva** (con los rechazos de RF-05) | `RegistrarReservaService.registrar` | huésped, tipo, fechas, personas | RN-03 salida > entrada · RN-04 entrada ≥ hoy · RN-05 huésped y tipo existen · RN-02 personas ≤ capacidad · RN-01 habitación sin noches ocupadas: se toma la **libre de menor número** | `huespedes.obtener_por_id`, `tipos.buscar_por_id`, `habitaciones.buscar_libres_por_tipo_y_rango`, `reservas.guardar`, `reservas.buscar_por_id` | 201 con id real, habitación asignada, noches, tarifa y total; estado CONFIRMADA | 400, 404, 409, 422 |
| 1 (confirmación) | RF-04: consultar la reserva creada | `ConsultarReservaService.consultar` | id de reserva | id entero positivo; distinguir encontrada de ausente | `reservas.buscar_por_id`, `habitaciones.obtener_por_id`, `tipos.buscar_por_id`, `huespedes.obtener_por_id` | 200 con la reserva | 400, 404 |
| **2** | **RF-02 Consultar disponibilidad** | `ConsultarDisponibilidadService.consultar` | tipo, fechas, personas | RN-03 · RN-04 · RN-05 (tipo existe) · RN-02 (capacidad) | `tipos.buscar_por_id`, `habitaciones.buscar_libres_por_tipo_y_rango` | 200 con la lista de libres (puede venir vacía) | 400, 404, 422 |

La consulta por id corresponde a RF-06 del segundo corte. Aquí no es un tercer RF priorizado: es la
**confirmación de RF-04**. Sirve para mostrar la reserva creada y para verificar si una creación quedó
guardada antes de repetirla (sección 7).

### Transacción y recursos

- **Quién la administra:** el servicio. `RegistrarReservaService` llama a `proveedor.escribir(caso)`
  (`app/persistence/proveedor.py`), que abre **una** transacción de MongoDB para todo el caso de uso.
- **Confirmación:** se confirma al terminar `caso` sin errores. La API envía el **201 solo después de
  confirmar**.
- **Reversión:** cualquier excepción (regla incumplida o fallo inesperado) **aborta** la transacción completa,
  incluido el contador de ids.
- **Concurrencia:** si dos solicitudes chocan, MongoDB marca un conflicto transitorio y la transacción
  se reintenta completa. Si el índice único de noches rechaza la habitación (otra solicitud la tomó),
  el servicio prueba con la siguiente libre en una **transacción nueva**, hasta 10 intentos. Si no queda
  ninguna, responde 409.
- **Recursos:** cada transacción usa su propia sesión y se cierra al salir, aun con error. El cliente de
  MongoDB es compartido y mantiene su propio pool de conexiones.
- **Lecturas:** RF-02 y la consulta por id usan `proveedor.leer`, que nunca escribe.

### Separación por capas

- **API (`app/api`):** recibe HTTP, valida el formato y traduce los errores. No tiene reglas ni MongoDB.
- **Servicios (`app/services`):** reglas de negocio. No conocen HTTP ni MongoDB; reciben un
  `ProveedorRepositorios`, así que se prueban con uno en memoria (RNF-06).
- **Persistencia (`app/persistence`):** único lugar que usa pymongo. También traduce las caídas de
  conexión a `BaseNoDisponibleError`.

---

## 2. Contratos

**URL base:** `http://127.0.0.1:8000` · **Documentación interactiva:** `http://127.0.0.1:8000/docs`

**Convenciones:**
- Nombres JSON en `snake_case` e identificadores enteros.
- Fechas `AAAA-MM-DD`.
- Dinero como número en pesos.
- Todos los errores controlados tienen la forma `{"detail": "...", "codigo": "..."}`. Los errores de
  formato agregan además una lista `errores` con cada campo.

| RF | Método y ruta | Entrada | Éxito | Errores | Servicio |
|---|---|---|---|---|---|
| RF-02 | `GET /api/disponibilidad` | Query: `id_tipo` (entero > 0), `fecha_entrada`, `fecha_salida` (AAAA-MM-DD), `personas` (entero ≥ 1) | **200** con tipo, capacidad, tarifa, noches y `habitaciones_disponibles` (lista, puede estar vacía) | **400** `DATOS_INVALIDOS` o `FECHAS_INVALIDAS` · **404** `NO_ENCONTRADO` (tipo) · **422** `CAPACIDAD_EXCEDIDA` · **503** `BD_NO_DISPONIBLE` | `ConsultarDisponibilidadService` |
| RF-04 | `POST /api/reservas` | JSON: `id_huesped`, `id_tipo`, `fecha_entrada`, `fecha_salida`, `numero_personas`. No se aceptan campos extra. El id, la habitación, el total y el estado los define el backend. | **201** con la reserva y cabecera `Location: /api/reservas/{id}` | **400** `DATOS_INVALIDOS` o `FECHAS_INVALIDAS` · **404** `NO_ENCONTRADO` (huésped o tipo) · **409** `SIN_DISPONIBILIDAD` · **422** `CAPACIDAD_EXCEDIDA` · **503** | `RegistrarReservaService` |
| RF-04 | `GET /api/reservas/{id_reserva}` | id entero positivo en la ruta; sin cuerpo | **200** con la reserva | **400** `DATOS_INVALIDOS` · **404** `NO_ENCONTRADO` · **503** | `ConsultarReservaService` |
| — | `GET /api/salud` | — | **200** `{"estado":"ok","base":"marea_test"}` | **503** si MongoDB no responde | — |

Cualquier fallo no previsto responde **500** `ERROR_INTERNO` con un mensaje genérico. El detalle técnico
solo queda en el registro del servidor y nunca se envía al cliente.

**Por qué 400 y no 422 en los errores de formato.** FastAPI responde 422 por defecto, pero en nuestro
contrato **422 ya significa `CAPACIDAD_EXCEDIDA`** (documento del segundo corte, tabla 8). Para que
la pantalla los distinga, los errores de formato se configuraron como **400 `DATOS_INVALIDOS`** en
`app/api/errores.py`, y `/docs` se ajustó para no anunciar el 422 automático.

### Ejemplos (salida real del backend)

Todos los ejemplos están en `evidencias/semana14/contratos_ejemplos.md`, generado con
`python -m scripts.demo_api` sobre la base recién creada.

**RF-04: creación (CA-01)**

```http
POST /api/reservas
Content-Type: application/json

{ "id_huesped": 1, "id_tipo": 2, "fecha_entrada": "2026-12-20", "fecha_salida": "2026-12-23", "numero_personas": 3 }
```
```http
HTTP 201 Created
Location: /api/reservas/4

{
  "id_reserva": 4,
  "estado": "CONFIRMADA",
  "huesped": { "id_huesped": 1, "nombre": "Ana Torres" },
  "habitacion": { "id_habitacion": 13, "numero": "201", "tipo": "Familiar" },
  "fecha_entrada": "2026-12-20",
  "fecha_salida": "2026-12-23",
  "noches": 3,
  "numero_personas": 3,
  "tarifa_noche": 200000,
  "total": 600000
}
```

El id 4 sale porque la base de prueba trae 3 reservas. En las pruebas siempre se usa el id que el
backend devuelve de verdad.

**RF-04: sin disponibilidad (CA-03)**, cuando ya están ocupadas las 4 Suites:
```http
HTTP 409 Conflict
{ "detail": "No hay habitaciones disponibles para esas fechas.", "codigo": "SIN_DISPONIBILIDAD" }
```

**RF-04: capacidad excedida (CA-05)** y **fechas inválidas (CA-06)**:
```http
HTTP 422 Unprocessable Content
{ "detail": "El tipo Estándar admite como máximo 2 personas.", "codigo": "CAPACIDAD_EXCEDIDA" }

HTTP 400 Bad Request
{ "detail": "La fecha de salida debe ser posterior a la de entrada.", "codigo": "FECHAS_INVALIDAS" }
```

**RF-04: campo faltante**
```http
HTTP 400 Bad Request
{ "detail": "Datos de entrada inválidos. id_huesped: es obligatorio", "codigo": "DATOS_INVALIDOS",
  "errores": [ { "campo": "id_huesped", "mensaje": "es obligatorio" } ] }
```

**RF-04: consultar la reserva creada**: `GET /api/reservas/4` responde 200 con el mismo JSON de la
creación.

**RF-04: reserva ausente**:
```http
GET /api/reservas/999999
HTTP 404 Not Found
{ "detail": "La reserva no existe.", "codigo": "NO_ENCONTRADO" }
```

**RF-02: disponibilidad (CA-02)**
```http
GET /api/disponibilidad?id_tipo=3&fecha_entrada=2026-12-21&fecha_salida=2026-12-22&personas=2
```
```http
HTTP 200 OK
{
  "id_tipo": 3, "tipo": "Suite", "capacidad": 3, "tarifa_noche": 280000,
  "fecha_entrada": "2026-12-21", "fecha_salida": "2026-12-22", "noches": 1, "personas": 2,
  "habitaciones_disponibles": [
    { "id_habitacion": 22, "numero": "302" },
    { "id_habitacion": 23, "numero": "303" },
    { "id_habitacion": 24, "numero": "304" }
  ]
}
```

### Cambios frente al contrato del segundo corte

| Antes (segundo corte) | Ahora (semana 14) | Motivo |
|---|---|---|
| JSON en camelCase (`huespedId`, `fechaEntrada`) | `snake_case` (`id_huesped`, `fecha_entrada`) | Convención pedida en la guía de la semana 14 |
| Error `{"codigo","mensaje"}` | `{"detail","codigo"}` | `detail` es el campo que usa la guía y FastAPI; se conservan los mismos códigos internos |
| Validación de formato sin código propio | 400 `DATOS_INVALIDOS` | Para no confundirla con 422 `CAPACIDAD_EXCEDIDA` |
| Respuesta de disponibilidad sin fechas ni noches | Incluye `fecha_entrada`, `fecha_salida`, `noches` y `personas` | Para que la pantalla muestre el resumen sin recalcular |
| `POST /api/auth/login`, `GET/POST /api/huespedes` | No se implementan | RF-01 y RF-03 quedaron fuera del alcance en la semana 13; se usan huéspedes precargados |

Las rutas heredadas (`/login`, `/rooms`, `/reservations`…) siguen en `app/main.py`, pero **están fuera
del corte**: la API del corte no las usa y `verificar_capas` las lista aparte.

---

## 3. Pruebas funcionales (actividad 3)

**Estado inicial de cada prueba** (lo crea `scripts/reset_db`, automáticamente antes de cada una):

- 24 habitaciones: Estándar 101–112 (ids 1–12), Familiar 201–208 (ids 13–20) y Suite 301–304 (ids 21–24).
- Huéspedes 1 a 3.
- Reservas:
  - id 1: Suite 301, del 20 al 23 de diciembre de 2026, CONFIRMADA.
  - id 2: Suite 302, mismas fechas, CANCELADA.
  - id 3: Estándar 101, del 10 al 12 de diciembre, CONFIRMADA.
- Contador de reservas en 3.

El caso exitoso cambia los datos, así que cada prueba arranca desde una base recién creada.

**Resultado obtenido:** las 69 pruebas pasan (`evidencias/semana14/pytest_resultado.txt`). En
todos los escenarios de la tabla, lo obtenido coincide con lo esperado.

| RF | Escenario | Pasos | Resultado esperado | Prueba |
|---|---|---|---|---|
| RF-04 | Válido (CA-01) | POST Familiar, 3 personas, del 20 al 23 de diciembre | 201, id 4, habitación 201, total 600 000; la misma reserva se recupera desde **otra conexión** | `test_rf04_valido_201_y_se_recupera_desde_otra_conexion` |
| RF-04 | Sin disponibilidad (CA-03) | Se ocupan 302, 303 y 304 del 21 al 22 y se pide otra Suite | 409 `SIN_DISPONIBILIDAD`; misma cantidad de reservas antes y después | `test_rf04_rechazo_409_sin_disponibilidad_no_cambia_registros` |
| RF-04 | Capacidad (CA-05) | Estándar con 3 personas | 422 `CAPACIDAD_EXCEDIDA`; sin registro nuevo | `test_rf04_capacidad_excedida_422` |
| RF-04 | Fechas (CA-06, RN-04) | Salida antes que la entrada · mismo día · entrada en el pasado | 400 `FECHAS_INVALIDAS`; sin registro nuevo | `test_rf04_fechas_invalidas_400` (3 casos) |
| RF-04 | Huésped inexistente | `id_huesped` 999 | 404; sin registro huérfano y contador sin avanzar | `test_rf04_huesped_inexistente_404_sin_registro_huerfano` |
| RF-04 | Tipo inexistente | `id_tipo` 9 | 404 | `test_rf04_tipo_inexistente_404` |
| RF-04 | Entrada mal formada | Falta un campo · fecha `20/12/2026` · 0 personas · campo `huespedId` | 400 `DATOS_INVALIDOS` con el campo señalado; sin registro nuevo | `test_rf04_entrada_mal_formada_400` (4 casos) |
| RF-04 | Rango contiguo (CA-04) | Suite desde el 23 (día en que sale la reserva de la 301) | 201 con la 301 | `test_rf04_inicio_el_dia_de_salida_de_otra_se_permite` |
| RF-04 | Consultar por id | GET con el id recién creado | 200 con los mismos datos; el documento en la base no cambia | `test_rf04_consultar_por_id_200_no_modifica` |
| RF-04 | Reserva ausente | Se verifica que 999999 no existe y se consulta | 404 controlado; la API sigue respondiendo | `test_rf04_consultar_id_inexistente_404_y_api_sigue_disponible` |
| RF-04 | Id inválido | `abc`, `0`, `-3`, `1.5` | 400 `DATOS_INVALIDOS`, sin error interno | `test_rf04_consultar_id_invalido_400` (4 casos) |
| RF-02 | Válido (CA-02) | Suites del 21 al 22, 2 personas | 200 con 302, 303 y 304 (la 301 no aparece; la 302 cancelada no bloquea) | `test_rf02_valido_suites_21_22` |
| RF-02 | Refleja una reserva nueva | Se reserva una Suite y se vuelve a consultar | 200 con 303 y 304 | `test_rf02_refleja_reserva_recien_creada` |
| RF-02 | Sin habitaciones | Se ocupan todas y se consulta | 200 con lista vacía | `test_rf02_sin_habitaciones_200_lista_vacia` |
| RF-02 | Tipo inexistente · capacidad · fechas | `id_tipo` 9 · 4 personas en Suite · fechas al revés | 404 · 422 · 400 | `test_rf02_tipo_inexistente_404`, `…capacidad_excedida_422`, `…fechas_invalidas_400` |
| RF-02 | Parámetros mal formados | Falta un parámetro · fecha `mañana` | 400 `DATOS_INVALIDOS` | `test_rf02_parametro_faltante_o_mal_formado_400` |
| RF-02 | Solo lectura | Consultar y contar reservas | Misma cantidad antes y después | `test_rf02_consultar_no_modifica_datos` |

También se repitió la prueba de lectura y escritura de la semana 13 (`tests/test_persistencia.py`,
15 pruebas), como pide el paso 2 de “Antes de programar”.

---

## 4. Matriz RF–RNF con evidencias (actividad 4)

Se conservan los identificadores, las características ISO/IEC 25010:2023, las condiciones y las metas
de la semana 13.

| RF / RNF | Calidad ISO/IEC 25010:2023 | Escenario y meta | Resultado observado | Estado | Evidencia |
|---|---|---|---|---|---|
| RF-02, RF-04 / **RNF-01** | Eficiencia de desempeño / comportamiento temporal | 10 usuarios concurrentes × 20 consultas `GET /api/disponibilidad` (200 solicitudes) con 5 003 reservas en la base. Se mide la respuesta HTTP completa desde el cliente. Meta: **p95 ≤ 2 000 ms** y todas 200. | p95 **38 ms**, máximo 69 ms, promedio 28 ms; 200 de 200 respondieron 200. Referencia: 20 consultas consecutivas de un cliente, máximo 11,9 ms. | **Cumple**, medido en el equipo del grupo (Python 3.12, MongoDB 8.0.34). La creación (POST) no forma parte de este escenario: su tiempo se observará desde la pantalla en la semana 15. | `evidencias/semana14/rnf01_api.json` · `python -m scripts.medir_api` |
| RF-04 / **RNF-03** | Fiabilidad / tolerancia a fallos | Por API, se provoca un fallo **después** de guardar y antes de confirmar. Meta: 0 documentos parciales, contador sin avanzar y respuesta controlada. | 500 `ERROR_INTERNO` con mensaje genérico; 0 documentos nuevos; contador igual; el detalle técnico no se envía al cliente. | **Cumple** | `test_rnf03_fallo_despues_de_guardar_responde_500_generico_sin_datos_parciales` |
| RF-02, RF-04 / **RNF-06** | Mantenibilidad / modularidad y capacidad para ser probado | Servicios con repositorios **simulados**, con `MongoClient` bloqueado (cualquier conexión hace fallar la prueba). Comprobaciones: registro válido, sin disponibilidad, capacidad, huésped inexistente, fechas, reintento, consulta existente, consulta ausente e id inválido, más RF-02 (válida, vacía, tipo, capacidad, fechas). En los rechazos **no se invoca `guardar`** y las consultas **solo leen**. Meta: todas pasan sin conexión real y hay 0 accesos a MongoDB fuera de la capa de persistencia. | 20 pruebas aisladas pasan (17 de servicios y 3 de errores de la API y CORS); 0 hallazgos de acceso a MongoDB fuera de `app/persistence`. | **Cumple** | `tests/test_servicios_aislados.py` · `evidencias/semana14/rnf06_servicios_aislados.txt` · `evidencias/semana14/verificar_capas.txt` |
| RF-04 / **RNF-08** | Fiabilidad / ausencia de fallos | 10 `POST /api/reservas` simultáneos por la **única** Suite libre (CA-07). Meta: exactamente 1 respuesta 201, 9 respuestas 409 y 1 sola reserva activa. | 1 × 201, 9 × 409, 1 reserva activa. | **Cumple a nivel de API.** **Pendiente semana 15:** repetirlo de extremo a extremo desde la pantalla. | `test_rnf08_diez_solicitudes_simultaneas_por_la_ultima_suite` |

Un endpoint que funciona no demuestra por sí solo un RNF. Por eso cada fila tiene su propia prueba o
medición, con su meta.

---

## 5. Ejecución

### Requisitos

| Herramienta | Versión |
|---|---|
| Python | ≥ 3.10 (API probada en 3.13; la persistencia también en 3.12) |
| MongoDB | 8.0 en modo replica set `rs0` (`docker compose up -d`; ver `README_SEMANA13.md`, sección 4) |
| Dependencias | `requirements-corte.txt`: pymongo, python-dotenv, pytest, fastapi, uvicorn, httpx |

### Variables (opcionales, en `.env`)

| Variable | Por defecto | Uso |
|---|---|---|
| `MONGO_URI` | `mongodb://127.0.0.1:27017/?replicaSet=rs0` | Servidor MongoDB |
| `MONGO_DB_PRUEBA` | `marea_test` | Base del corte. `reset_db` la borra y la recrea; nunca toca `hotel_db` |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Orígenes que pueden llamar a la API (Vite) |

### Puertos

- **27017:** MongoDB.
- **8000:** la API del corte.
- **8001:** lo usa solo `medir_api` mientras mide.

### Comandos

```bash
docker compose up -d                         # MongoDB 8.0 en replica set
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-corte.txt

python -m scripts.reset_db                   # base de prueba con su estado inicial
uvicorn app.api.app:app --reload --port 8000 # API del corte → http://127.0.0.1:8000/docs

# en otra terminal, con el venv activo:
pytest -v                                    # 69 pruebas (persistencia, API, aisladas, correos)
pytest -v -m sin_base                        # solo las 20 aisladas de RNF-06
python -m scripts.demo_api                   # ejemplos de contrato → evidencias/semana14/
python -m scripts.medir_api                  # RNF-01 por HTTP → evidencias/semana14/rnf01_api.json
python -m scripts.verificar_capas            # RNF-06: acceso a MongoDB solo en persistencia
```

**Reiniciar los datos de prueba:** `python -m scripts.reset_db`. Las pruebas lo hacen solas antes de
cada caso. `medir_api` y `demo_api` restauran la base al terminar.

`app.api.app` levanta **solo el corte** y no necesita las dependencias de las rutas heredadas.
`app/main.py` (la aplicación heredada más el corte) requiere además lo de `instaladores.txt`.

### Hallazgo: MongoDB se cerraba a mitad de las pruebas

**Qué pasó:** en el equipo del grupo, la primera corrida completa falló a la mitad. MongoDB se cerró
con `Too many open files` y `WT_PANIC`; el registro está en `docker logs proyecto-master-mongo-1`.

**Causa:** antes de cada prueba, `reset_db` borraba y recreaba las colecciones y sus índices. MongoDB
no elimina de inmediato los archivos de lo borrado, así que se acumularon cientos (más de 1 500 en
la carpeta de datos). El contenedor alcanzó su límite de archivos abiertos.

**Corrección:**
1. `docker-compose.yml` sube el límite a 64 000 (`ulimits.nofile`, el valor que recomienda MongoDB)
   y reinicia el contenedor si se cae (`restart: unless-stopped`).
2. Las pruebas recrean el esquema **una sola vez** por corrida y, entre una prueba y otra, solo
   vacían y recargan los documentos (`reset(completo=False)`).

**Resultado:** cada corrida completa deja unos 16 archivos nuevos en vez de cientos, y tarda menos.
`python -m scripts.reset_db` sigue recreando todo.

Después de cambiar `docker-compose.yml` hay que volver a crear el contenedor:
`docker compose up -d --force-recreate`.

---

## 6. Roles del equipo

| Tarea | Responsable |
|---|---|
| Implementa servicios y API | _(completar)_ |
| Prueba (funcionales y RNF) | _(completar)_ |
| Revisa (código y contratos) | _(completar)_ |

Los dos integrantes deben poder explicar ambos RF.

---

## 7. Relevo a la interfaz (semana 15)

- **Contratos:** los de la sección 2. La pantalla puede abrir `http://127.0.0.1:8000/docs` para
  probarlos.
- **Flujo previsto de la pantalla “Nueva reserva”:**
  1. `GET /api/disponibilidad` con tipo, fechas y personas.
  2. Si la lista no está vacía, `POST /api/reservas` con el huésped.
  3. Mostrar `id_reserva`, habitación, noches y total. `GET /api/reservas/{id}` sirve para volver a
     mostrarla.
- **Mensajes:** mostrar el `detail` de cada error. El `codigo` sirve para decidir qué hacer:
  - `FECHAS_INVALIDAS` y `DATOS_INVALIDOS`: marcar el campo, usando `errores[].campo`.
  - `CAPACIDAD_EXCEDIDA`: sugerir otro tipo.
  - `SIN_DISPONIBILIDAD`: sugerir otras fechas.
  - `BD_NO_DISPONIBLE` y `ERROR_INTERNO`: “intente más tarde”.
- **Datos disponibles:**
  - huéspedes 1 (Ana Torres), 2 (Carlos Méndez) y 3 (Laura Smith);
  - tipos 1 Estándar (cap. 2), 2 Familiar (cap. 4) y 3 Suite (cap. 3);
  - fechas de diciembre de 2026.

  Antes de cada demostración se ejecuta `reset_db`.
- **CORS:** ya permite `http://localhost:5173` y `http://127.0.0.1:5173`, los puertos de Vite. Otro
  origen se agrega en `CORS_ORIGINS`.
- **Si se pierde la respuesta de un POST,** por ejemplo porque se cayó la red: la pantalla **no debe
  repetir la reserva automáticamente**. Debe avisar y volver a consultar la disponibilidad del mismo
  tipo y fechas, para ver si la habitación quedó ocupada. Una consulta de reservas por huésped haría
  esta verificación exacta; queda como decisión abierta para la semana 15.
- **RNF pendientes para la semana 15:**
  - **RNF-08** de extremo a extremo (CA-07 desde la pantalla);
  - el tiempo de creación observado desde la interfaz (RNF-01);
  - los escenarios CA-01 a CA-07 recorridos desde la pantalla.

---

## 8. Correos que no se repiten

| Dónde | Cómo se impide | Respuesta |
|---|---|---|
| Registro de usuarios del login (`POST /register`, ruta heredada, base `hotel_db`) | Antes de guardar se busca el correo **sin distinguir mayúsculas ni espacios** (`Ana@Correo.com ` = `ana@correo.com`). Además hay un **índice único** `ux_usuario_email`, que se crea al arrancar `app/main.py` y frena también dos registros simultáneos. Los correos nuevos se guardan en minúsculas. | **409** `{"detail": "Ya existe una cuenta con ese correo."}` (antes era 400). El login también acepta el correo con cualquier combinación de mayúsculas. |
| Pantalla de registro (`frontend/src/pages/Login.tsx`) | Muestra el mensaje real del backend en lugar de “Error al registrar”. | El usuario ve “Ya existe una cuenta con ese correo.” |
| Huéspedes del corte (`marea_test.huespedes`) | Índice único `ux_huesped_correo`, sin distinguir mayúsculas. Solo aplica si el huésped tiene correo: varios pueden no tenerlo. | La base rechaza el documento repetido. |

**Pruebas** (`tests/test_correos_unicos.py`):
- huésped con correo repetido en otras mayúsculas: rechazado;
- varios huéspedes sin correo: permitidos;
- registro repetido: 409 y un solo usuario en la base;
- login con el correo en mayúsculas: funciona;
- 5 registros simultáneos con el mismo correo: 1 respuesta 201 y 4 respuestas 409.

Las pruebas del registro usan la colección `marea_test.usuarios_prueba`, nunca `hotel_db`. Si no están
instaladas las dependencias del login (`instaladores.txt`), esas 3 pruebas se **omiten** (`skipped`).

**Si la base `hotel_db` ya tiene correos repetidos de antes,** MongoDB no puede crear el índice único:
lo avisa en el registro del servidor y la verificación del registro sigue funcionando. Para crear el
índice, primero hay que borrar los duplicados.

**Corrección relacionada:** `passlib` (usado para cifrar contraseñas) no funciona con `bcrypt` 5.0. El
registro respondía 500 antes de llegar a guardar. Se fijó `bcrypt==4.0.1` en `instaladores.txt`.
