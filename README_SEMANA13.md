# MareaDorada Pro v1.0 — Semana 13: base de datos y persistencia del corte vertical

**Arquitectura de Sistemas I** · Docente: Ing. Elías Buitrago Bolivar
**Integrantes:** Erick Genaldo Flores · Juan David Arroyave

Corte vertical: **Crear una reserva** (actor: recepcionista). Esta semana se prepara la base técnica:
dos RF priorizados, sus RNF verificables según ISO/IEC 25010:2023, una base mínima con datos de prueba
y operaciones de persistencia comprobadas contra **MongoDB real** (replica set de un nodo).

**Stack:** Python 3.10+ · pymongo 4.19 · MongoDB 8.0 en modo replica set · pytest.

---

## 1. Los dos RF y su prioridad (Actividad 1)

Se conservan los identificadores del documento del segundo corte (*MareaDorada Pro v1.0 — Corte vertical*,
sección 2.2) y el alcance de la plantilla del grupo (Tabla 1).

| Orden | RF | Actor | Acción | Resultado observable |
|---|---|---|---|---|
| **1** | **RF-04. Crear reserva** (incluye los rechazos de RF-05) | Recepcionista | Envía huésped, tipo de habitación, fechas y número de personas. | Reserva CONFIRMADA con identificador real, habitación asignada, noches, tarifa por noche y total; o rechazo controlado (fechas inválidas, capacidad excedida, sin disponibilidad). |
| **2** | **RF-02. Consultar disponibilidad** | Recepcionista | Indica rango de fechas, tipo y número de personas. | Lista de habitaciones del tipo sin reservas activas solapadas en el rango (lista vacía si no hay). |

**Justificación del orden** (criterios del segundo corte: valor para el actor y relevancia arquitectónica,
más esfuerzo, riesgo y dependencias):

| Criterio | RF-04 Crear reserva | RF-02 Consultar disponibilidad |
|---|---|---|
| Valor para el actor | Alto: es la tarea central de recepción y la que hoy produce dobles reservas. | Alto: evita revisar a mano qué habitaciones están libres. |
| Relevancia arquitectónica | Alta: escritura transaccional, regla RN-01 reforzada por un índice único, manejo de concurrencia (riesgo R1). | Media: lectura con consulta de rango; sin escritura. |
| Esfuerzo | Medio. | Bajo. |
| Riesgo | Alto (R1: doble reserva concurrente). | Bajo. |
| Dependencia | Usa la misma consulta de habitaciones libres que RF-02 para asignar la habitación. | Ninguna; la consulta la reutiliza RF-04. |

**Decisión:** ambos tienen valor alto. RF-04 va primero porque concentra el riesgo técnico principal (R1) y
conviene enfrentarlo pronto; su dependencia con RF-02 se resuelve en la persistencia, porque los dos usan
la misma operación `buscar_libres_por_tipo_y_rango`. Así RF-02 queda casi resuelto al construir RF-04.

**Qué queda fuera:** autenticación y roles (RF-01), registro de huéspedes (RF-03; se usan huéspedes
precargados), modificación y cancelación de reservas, check-in/check-out, tarifas por temporada,
facturación, reportes, OTAs y aplicación móvil.

---

## 2. Matriz RF–RNF con ISO/IEC 25010:2023 (Actividad 2)

Formato: *identificador y RF + característica/subcaracterística + condición + medida + umbral + evidencia*.
Los umbrales los define el equipo según el contexto del Resort (24 habitaciones, recepción con pocos
puestos); la norma no los impone. Se reutilizan RNF-01, RNF-03 y RNF-06 del segundo corte y se agrega
RNF-08, que formaliza el riesgo R1 y el escenario CA-07.

| RNF | RF | ISO/IEC 25010:2023 | Condición de prueba | Medida y umbral | Evidencia | Semana |
|---|---|---|---|---|---|---|
| **RNF-01** | RF-02, RF-04 | Eficiencia de desempeño / comportamiento temporal | Entorno local documentado, base con ≥ 5 000 reservas, un cliente, 20 consultas consecutivas de disponibilidad. | **Sem 1 (repositorio):** cada consulta ≤ 200 ms. **Sem 2–3 (API):** p95 ≤ 2 s con 10 usuarios concurrentes. | `evidencias/rnf01_tiempos.json` (tiempos, datos y entorno). | 1 (parcial) · 2–3 |
| **RNF-03** | RF-04 | Fiabilidad / tolerancia a fallos | Se provoca un error después de guardar la reserva y antes de confirmar la transacción. | 0 documentos parciales persistidos y el contador de ids sin avanzar (100 % de los casos). Un rechazo aborta la transacción y se puede reintentar en una nueva. | `test_rnf03_*` en `evidencias/pytest_resultado.txt`. | 1 · se repite en 2 con el servicio |
| **RNF-06** | RF-02, RF-04 | Mantenibilidad / modularidad y capacidad para ser probado | Revisión estática del código y contratos de repositorio. | 0 accesos directos a MongoDB (pymongo, colecciones, `find`, `insert_one`…) fuera de `app/persistence` y `db` en el código del corte. Cada servicio probado con repositorio simulado: ≥ 1 caso válido y ≥ 1 de rechazo o ausencia. | `evidencias/verificar_capas.txt`; contratos en `app/persistence/contracts.py`. | 1 (contratos y verificación) · 2 (pruebas de servicios) |
| **RNF-08** | RF-04 | Fiabilidad / ausencia de fallos | 10 solicitudes simultáneas reservan la misma habitación y las mismas fechas. | Exactamente 1 reserva persistida y 9 rechazos controlados; 0 reservas solapadas. | `test_rnf08_*` en `evidencias/pytest_resultado.txt`. | 1 (repositorio) · 3 (de extremo a extremo, CA-07) |

**Distinción regla / RNF.** “No reservar una habitación con fechas solapadas” (RN-01) y “la capacidad no
se supera” (RN-02) son **reglas de negocio de RF-04**; las decide el servicio en la semana 2. Los RNF
expresan condiciones de calidad y cómo comprobarlas: tiempo de respuesta, ausencia de datos parciales,
comportamiento correcto bajo concurrencia y separación por capas. La base de datos **refuerza** RN-01 y
RN-03 con su índice único y su validador, pero no reemplaza la regla del servicio.

---

## 3. Datos y persistencia (Actividad 3)

### 3.1 Cambio de stack frente al segundo corte

El documento del segundo corte proponía **Spring Boot + PostgreSQL**. El corte se implementa en
**Python + MongoDB** por estas razones:

- El backend que ya existe en el repositorio es FastAPI (Python) y usa MongoDB (`hotel_db`). Mantener un
  solo lenguaje y un solo motor evita instalar y operar dos bases en el mismo sistema.
- MongoDB 8 ofrece transacciones ACID de varios documentos (en replica set), que es lo que exige RF-04.
- La regla crítica RN-01 se puede reforzar en la base con un **índice único parcial**, equivalente a la
  restricción de exclusión que motivaba PostgreSQL (ver 3.3).

Costo asumido: MongoDB **debe correr como replica set** (basta uno de un solo nodo) para tener
transacciones, y no tiene claves foráneas, así que el repositorio las verifica dentro de la transacción.

### 3.2 Datos mínimos (colecciones)

La persistencia del corte usa una base **separada**: `marea_test` (variable `MONGO_DB_PRUEBA`). Así
`reset_db` nunca toca `hotel_db`, que es la de las rutas heredadas.

| Colección | Campos obligatorios e integridad | Sirve a |
|---|---|---|
| `tipos_habitacion` | `_id` int, `nombre` único, `capacidad_max` ≥ 1, `tarifa_noche` decimal > 0 | RF-02 (filtro por tipo), RF-04 (capacidad RN-02 y tarifa para el total) |
| `habitaciones` | `_id` int, `numero` único, `id_tipo`, `estado` ∈ {LIBRE, RESERVADA, OCUPADA, EN_LIMPIEZA} | RF-02 (lista de libres), RF-04 (habitación asignada) |
| `huespedes` | `_id` int, `nombre`, `documento` único | RF-04 (el huésped debe existir, RN-05) |
| `reservas` | `_id` int, `id_huesped`, `id_habitacion`, fechas, `noches` (lista de noches ocupadas), `numero_personas` ≥ 1, tarifa y total > 0, `estado` ∈ {CONFIRMADA, EN_CURSO, FINALIZADA, CANCELADA}, `creada_en` | RF-04 (escritura y lectura), RF-02 (determina ocupación) |
| `contadores` | `_id: "reserva"`, `valor` | Ids enteros consecutivos para las reservas |

Relaciones (por referencia de id): `tipos_habitacion 1—N habitaciones`, `habitaciones 1—N reservas`,
`huespedes 1—N reservas`.

### 3.3 Cómo se refuerza la integridad en MongoDB

| En PostgreSQL (modelo previo) | En MongoDB (este corte) | Regla |
|---|---|---|
| `NOT NULL`, tipos y `CHECK` | Validador `$jsonSchema` por colección (`validationLevel: strict`) | Datos completos y válidos |
| `CHECK (fecha_salida > fecha_entrada)` | `$expr: {$gt: ["$fecha_salida", "$fecha_entrada"]}` en el validador de `reservas` | RN-03 |
| `UNIQUE` | Índices únicos (`nombre`, `numero`, `documento`) | — |
| Restricción de exclusión sobre `daterange` | Índice único **parcial y multiclave** `ux_reserva_sin_solape` sobre (`id_habitacion`, `noches`), solo para reservas CONFIRMADA o EN_CURSO: dos reservas activas de la misma habitación no pueden compartir una noche. Funciona también con solicitudes simultáneas. Requiere MongoDB ≥ 6.0. | RN-01 |
| Claves foráneas | `guardar` verifica huésped y habitación dentro de la misma transacción | RN-05 |
| `SERIAL` | Colección `contadores` con `$inc` dentro de la transacción: si se aborta, el contador también vuelve atrás | Ids reales |
| `NUMERIC(12,2)` | `Decimal128` redondeado a centavos | Dinero sin errores de punto flotante |

El campo `noches` guarda cada noche del rango semiabierto [entrada, salida): la salida no cuenta como
noche. Por eso una reserva que entra el día en que otra sale no choca (CA-04).

**Otros cambios frente al modelo del segundo corte:** se omite la colección `usuario` (la autenticación
quedó fuera del alcance); los estados tienen valores cerrados; se agregan índices para la consulta de
disponibilidad (RNF-01).

### 3.4 Base reproducible

| Archivo | Contenido |
|---|---|
| `db/esquema.py` | Crea las colecciones, validadores e índices. Es idempotente: borra y recrea las del corte. |
| `db/datos_prueba.py` | Carga el estado inicial conocido y calcula los conteos de verificación. |
| `scripts/reset_db.py` | Ejecuta los dos anteriores y muestra la verificación. Funciona en Windows y Linux, sin `mongosh`. |

**Estado inicial (fechas de referencia, diciembre de 2026):**

- Tipos: Estándar (cap. 2, $120 000), Familiar (cap. 4, $200 000), Suite (cap. 3, $280 000).
- 24 habitaciones: Estándar 101–112, Familiar 201–208, Suite 301–304.
- Huéspedes: 1 Ana Torres (1020304050), 2 Carlos Méndez (79888777), 3 Laura Smith (P12345678).
- Reservas:
  - id 1: Suite **301**, del 2026-12-20 al 2026-12-23, **CONFIRMADA** (casos de solape).
  - id 2: Suite **302**, mismas fechas, **CANCELADA** (comprueba que una reserva inactiva no bloquea).
  - id 3: Estándar **101**, del 2026-12-10 al 2026-12-12, **CONFIRMADA**.
- Contador de reservas en 3: la siguiente reserva recibe el id 4.

Las fechas son futuras para cumplir RN-04. Si la entrega se reutiliza después de diciembre de 2026,
deben moverse en `db/datos_prueba.py` y en las pruebas.

### 3.5 Acceso separado: repositorios y contrato para la semana 2

| Repositorio | Operación | Entrada → Resultado | Para qué |
|---|---|---|---|
| `MongoTipoHabitacionRepository` | `buscar_por_id` | `id_tipo` → `TipoHabitacion \| None` | RF-02/RF-04: capacidad y tarifa |
| `MongoHabitacionRepository` | `buscar_libres_por_tipo_y_rango` | `id_tipo, entrada, salida` → `list[Habitacion]` | RF-02 (respuesta) y RF-04 (asignar la de menor número) |
| | `buscar_por_tipo`, `obtener_por_id` | → `list[Habitacion]`, `Habitacion \| None` | Apoyo a RF-04 |
| `MongoHuespedRepository` | `obtener_por_id` | `id_huesped` → `Huesped \| None` | RF-04: verificar existencia (RN-05) |
| `MongoReservaRepository` | `buscar_reservas_solapadas` | `id_habitacion, entrada, salida` → `list[Reserva]` | RF-04: el hecho con el que negocio decide disponibilidad |
| | `guardar` | `NuevaReserva` → `int` (id real) | RF-04: persistir. Lanza `SolapeReservaError`, `ReferenciaInexistenteError` o `DatosInvalidosError` |
| | `buscar_por_id` | `id_reserva` → `Reserva \| None` | RF-04: confirmación; representa la ausencia con `None` |

- Contratos (protocolos) en `app/persistence/contracts.py`; objetos en `models.py`; errores en `errors.py`.
  Los servicios dependen de los contratos, no de MongoDB.
- **Transacción** (`app/persistence/db.py`):
  - `unidad_de_trabajo()` abre una sesión con transacción: confirma si el bloque termina bien, aborta ante
    cualquier excepción y siempre cierra la sesión.
  - `en_transaccion(fn)` hace lo mismo y además **reintenta la transacción completa** ante errores
    transitorios (conflictos de escritura entre solicitudes simultáneas). Es la forma recomendada para
    escribir reservas.
  - En la semana 2 la usará el servicio `RegistrarReservaService`. Los repositorios nunca confirman ni abortan.
- **Sin SAVEPOINT:** en MongoDB un rechazo aborta la transacción completa. Para probar otra habitación
  libre (algoritmo de asignación, sección 10), el servicio abre una transacción **nueva**.
- **Separación:** el repositorio consulta y guarda; el servicio aplicará RN-01 a RN-05 en la semana 2;
  los endpoints y la pantalla del corte no acceden a MongoDB (verificado con `scripts/verificar_capas.py`).

> **Nota:** las rutas heredadas (`app/routes/`, `app/database.py`, `app/init_rooms.py`) todavía acceden a
> MongoDB directamente. `verificar_capas` las lista como **pendientes**, sin ocultarlas. En la semana 2 se
> reemplazan por los endpoints `GET /habitaciones/disponibilidad` y `POST /reservas`, que llamarán a los servicios.

---

## 4. Cómo repetir la verificación

### Requisitos

| Herramienta | Versión |
|---|---|
| Python | ≥ 3.10 (probado en 3.12 y 3.13) |
| MongoDB | 8.0 en modo **replica set** (mínimo 6.0, por el índice único parcial) |
| pymongo | 4.19.0 |
| pytest | ≥ 8.0 |

### Paso 1. MongoDB en modo replica set (elegir una opción)

**Opción A — Docker (recomendada).** Levanta MongoDB 8.0 como replica set `rs0` y lo inicia solo:

```bash
docker compose up -d
```

Si ya tiene un MongoDB local en el puerto 27017, deténgalo antes
(Linux: `sudo systemctl stop mongod`; Windows: `net stop MongoDB` como administrador).

**Opción B — Convertir el MongoDB local en replica set.** Sus bases (incluida `hotel_db`) se conservan.

1. Edite la configuración de `mongod` y agregue:
   ```yaml
   replication:
     replSetName: rs0
   ```
   - Linux: `/etc/mongod.conf`
   - Windows: `C:\Program Files\MongoDB\Server\8.0\bin\mongod.cfg`
2. Reinicie el servicio (Linux: `sudo systemctl restart mongod`; Windows: `net stop MongoDB` y `net start MongoDB`).
3. Inicie el replica set una sola vez:
   ```bash
   mongosh --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: '127.0.0.1:27017'}]})"
   ```

### Paso 2. Entorno Python y configuración

```bash
python -m venv venv
source venv/bin/activate                  # Windows: venv\Scripts\activate
pip install -r requirements-persistencia.txt
```

`.env.example` trae la configuración de ejemplo, sin credenciales reales. Si no tiene `.env`, cópielo
(`cp .env.example .env`; en Windows `copy .env.example .env`). Si ya tiene el `.env` del proyecto, sirve
tal cual: `MONGO_URI` apunta al mismo servidor y, si no define `MONGO_DB_PRUEBA`, la base de prueba es
`marea_test`. Sin `.env`, el valor por defecto es `mongodb://127.0.0.1:27017/?replicaSet=rs0`.

### Paso 3. Ejecutar

```bash
python -m scripts.reset_db              # recrea la base marea_test con su estado inicial
pytest -v tests/                        # 15 pruebas de integración contra MongoDB real
python -m scripts.reset_db
python -m scripts.demo_persistencia     # guardar, releer con un cliente nuevo, id inexistente, solape
python -m scripts.medir_disponibilidad  # RNF-01: carga 5 000 reservas, mide y restaura el estado inicial
python -m scripts.verificar_capas       # RNF-06: acceso a MongoDB solo en la capa de persistencia
```

`pytest.ini` agrega la raíz del proyecto al path, así que `pytest` y `python -m pytest` funcionan igual.

### Resultados esperados

- `reset_db`: `[ok] esquema ... en 'marea_test'`, `[ok] datos de prueba` y la verificación:
  Estándar 12, Familiar 8, Suite 4; 3 huéspedes; 2 reservas CONFIRMADA y 1 CANCELADA.
- `pytest`: **15 passed**.
- `demo_persistencia`:
  ```
  1) Suites libres 21-22 dic: ['302', '303', '304']
  2) Reserva guardada id=4 habitación=201 total=600000.00
  3) Recuperada desde un cliente nuevo: id=4 estado=CONFIRMADA 2026-12-20->2026-12-23 total=600000.00
  4) Reserva 999999: None
  5) Solape rechazado por la BD: La habitación ya tiene una reserva activa en ese rango
  ```
- `medir_disponibilidad`: `"cumple": true` (máximo ≤ 200 ms).
- `verificar_capas`: `OK ... (0 hallazgos)` y la lista de los 6 archivos heredados pendientes para la semana 2.

Si aparece *“MongoDB no está en modo replica set”*, falta el paso 1.

### Evidencias (`evidencias/`)

| Archivo | Qué demuestra |
|---|---|
| `pytest_resultado.txt` | Las 15 pruebas de integración, cada una con su RF/RNF/CA |
| `demo_consola.txt` | Lectura, escritura y persistencia real desde un cliente nuevo |
| `rnf01_tiempos.json` | 20 tiempos individuales, cantidad de reservas y entorno |
| `verificar_capas.txt` | 0 accesos a MongoDB fuera de la capa de persistencia en el código del corte |

---

## 5. Ficha RF–RNF del equipo

### RF-04 · Crear reserva (prioridad 1)

| Elemento | Respuesta del equipo |
|---|---|
| Identificador y enunciado | **RF-04.** El sistema creará una reserva CONFIRMADA para un huésped, con una habitación libre del tipo solicitado, calculando noches, tarifa por noche y total. Incluye los rechazos de RF-05: fechas inválidas, capacidad excedida o sin disponibilidad. |
| Actor y resultado esperado | Recepcionista. Obtiene el id real de la reserva, la habitación asignada, las fechas y el total; o un mensaje de rechazo claro. |
| Prioridad y justificación | **1.** Valor alto (tarea central y fuente de dobles reservas); relevancia arquitectónica alta (escritura transaccional, concurrencia, índice único de noches); concentra el riesgo R1, por eso va primero. Reutiliza la consulta de libres de RF-02. |
| RNF asociados | RNF-01, RNF-03, RNF-06, RNF-08 |
| ISO/IEC 25010:2023 | Eficiencia de desempeño / comportamiento temporal · Fiabilidad / tolerancia a fallos · Mantenibilidad / modularidad y capacidad para ser probado · Fiabilidad / ausencia de fallos |
| Condición, medida y umbral | RNF-01: API p95 ≤ 2 s con 10 usuarios y ≥ 5 000 reservas. RNF-03: 0 documentos parciales ante fallo. RNF-06: 0 accesos a MongoDB fuera de persistencia; servicio probado con repositorio simulado (≥ 1 caso válido y ≥ 1 de rechazo). RNF-08: 10 solicitudes simultáneas → 1 reserva, 9 rechazos, 0 solapes. |
| Prueba, evidencia y semana | Sem 1: `test_rf04_*`, `test_integridad_*`, `test_rnf03_*`, `test_rnf08_*`, `demo_consola.txt`. Sem 2: servicio con repositorio simulado y medición en la API. Sem 3: CA-01, CA-03, CA-05 a CA-07 de extremo a extremo. |
| Datos y operaciones de persistencia | Colecciones `reservas`, `habitaciones`, `tipos_habitacion`, `huespedes`, `contadores`. Operaciones `HuespedRepo.obtener_por_id`, `TipoHabitacionRepo.buscar_por_id`, `HabitacionRepo.buscar_libres_por_tipo_y_rango`, `ReservaRepo.buscar_reservas_solapadas`, `guardar`, `buscar_por_id`. |
| Resultado sem 1 y pendientes | ✔ Guardar y recuperar desde un cliente nuevo; id inexistente → `None`; índice único de noches, validador de fechas y verificación de huésped y habitación; atomicidad (incluido el contador) y reintento en transacción nueva; concurrencia 1/10. ☐ Pendiente sem 2: `RegistrarReservaService` con RN-01 a RN-05, cálculo del total, endpoint `POST /reservas`, pruebas con repositorio simulado. ☐ Sem 3: pantalla y flujo completo. |

### RF-02 · Consultar disponibilidad (prioridad 2)

| Elemento | Respuesta del equipo |
|---|---|
| Identificador y enunciado | **RF-02.** Dado un rango de fechas válido, un tipo de habitación y un número de personas, el sistema listará las habitaciones de ese tipo sin reservas solapadas en el rango. |
| Actor y resultado esperado | Recepcionista. Ve la lista de habitaciones libres (vacía si no hay). |
| Prioridad y justificación | **2.** Valor alto, pero menor relevancia arquitectónica (solo lectura) y bajo riesgo. Su consulta la construye y prueba RF-04, así que se completa con poco esfuerzo adicional. |
| RNF asociados | RNF-01, RNF-06 |
| ISO/IEC 25010:2023 | Eficiencia de desempeño / comportamiento temporal · Mantenibilidad / modularidad y capacidad para ser probado |
| Condición, medida y umbral | RNF-01 sem 1: 20 consultas con ≥ 5 000 reservas, cada una ≤ 200 ms en el repositorio. Sem 2–3: p95 ≤ 2 s en la API con 10 usuarios. RNF-06: como en RF-04. |
| Prueba, evidencia y semana | Sem 1: `test_rf02_*` (CA-02, CA-04, reserva cancelada) y `rnf01_tiempos.json`. Sem 2: `ConsultarDisponibilidadService` (validar fechas y capacidad, 422) y `GET /habitaciones/disponibilidad`. Sem 3: pantalla “Nueva reserva”, paso 1. |
| Datos y operaciones de persistencia | Colecciones `habitaciones`, `reservas`, `tipos_habitacion`. Operaciones `TipoHabitacionRepo.buscar_por_id` y `HabitacionRepo.buscar_libres_por_tipo_y_rango`. |
| Resultado sem 1 y pendientes | ✔ La 301 no aparece del 21 al 22; un rango contiguo no es solape; una reserva cancelada no bloquea; tipo sin reservas → 8 Familiares. RNF-01 (repositorio): máximo de pocos milisegundos con 5 003 reservas, muy por debajo de 200 ms. ☐ Pendiente sem 2: validación de capacidad en el servicio y medición en la API. |

---

### Antes de cerrar

Construiremos **RF-04 (crear reserva)** y **RF-02 (consultar disponibilidad)**, en ese orden, porque RF-04
concentra el valor y el riesgo de doble reserva, y comparte con RF-02 la consulta de habitaciones libres.
Esperamos respuestas rápidas (RNF-01), cero datos parciales (RNF-03), cero dobles reservas bajo
concurrencia (RNF-08) y capas separadas y fáciles de probar (RNF-06). Las pruebas de integración contra
MongoDB, la salida de consola y las mediciones guardadas en `evidencias/` lo verifican. La semana 2 parte
de estos mismos contratos.
