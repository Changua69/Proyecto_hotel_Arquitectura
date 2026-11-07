# MareaDorada Pro v1.0 — Semana 13: base de datos y persistencia del corte vertical

**Arquitectura de Sistemas I** · Docente: Ing. Elías Buitrago Bolivar
**Integrantes:** Erick Genaldo Flores · Juan David Arroyave

Corte vertical: **Crear una reserva** (actor: huesped). Esta semana se prepara la base técnica:
dos RF priorizados, sus RNF verificables según ISO/IEC 25010:2023, una base mínima con datos de prueba
y operaciones de persistencia comprobadas contra PostgreSQL real.

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
| Relevancia arquitectónica | Alta: escritura transaccional, regla RN-01 reforzada por restricción de exclusión, manejo de concurrencia (riesgo R1). | Media: lectura con consulta de rango; sin escritura. |
| Esfuerzo | Medio. | Bajo. |
| Riesgo | Alto (R1: doble reserva concurrente). | Bajo. |
| Dependencia | Usa la misma consulta de habitaciones libres que RF-02 para asignar la habitación. | Ninguna; la consulta la reutiliza RF-04. |

**Decisión:** ambos tienen valor alto. RF-04 va primero porque concentra el riesgo técnico principal (R1) y
conviene enfrentarlo pronto; su dependencia con RF-02 se resuelve en la persistencia, porque los dos usan
la misma operación `buscar_libres_por_tipo_y_rango`. Así RF-02 queda casi resuelto al construir RF-04.
RF-02 sigue dentro del alcance.

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
| **RNF-03** | RF-04 | Fiabilidad / tolerancia a fallos | Se provoca un error después de guardar la reserva y antes de confirmar la transacción. | 0 filas parciales persistidas (100 % de los casos). El rechazo de una habitación no aborta la transacción: se puede reintentar con otra. | `test_rnf03_*` en `evidencias/pytest_resultado.txt`. | 1 · se repite en 2 con el servicio |
| **RNF-06** | RF-02, RF-04 | Mantenibilidad / modularidad y capacidad para ser probado | Revisión estática del código y contratos de repositorio. | 0 sentencias SQL fuera de `app/persistence` y `db`. Cada servicio probado con repositorio simulado: ≥ 1 caso válido y ≥ 1 de rechazo o ausencia. | `evidencias/verificar_capas.txt`; contratos en `app/persistence/contracts.py`. | 1 (contratos y verificación) · 2 (pruebas de servicios) |
| **RNF-08** | RF-04 | Fiabilidad / ausencia de fallos | 10 solicitudes simultáneas reservan la misma habitación y las mismas fechas. | Exactamente 1 reserva persistida y 9 rechazos controlados; 0 reservas solapadas. | `test_rnf08_*` en `evidencias/pytest_resultado.txt`. | 1 (repositorio) · 3 (de extremo a extremo, CA-07) |

**Distinción regla / RNF.** “No reservar una habitación con fechas solapadas” (RN-01) y “la capacidad no
se supera” (RN-02) son **reglas de negocio de RF-04**; las decide el servicio en la semana 2. Los RNF
expresan condiciones de calidad y cómo comprobarlas: tiempo de respuesta, ausencia de datos parciales,
comportamiento correcto bajo concurrencia y separación por capas. La base de datos **refuerza** RN-01 y
RN-03 con restricciones, pero no reemplaza la regla del servicio.

---

## 3. Datos y persistencia (Actividad 3)

### 3.1 Datos mínimos

| Tabla | Claves y campos obligatorios | Sirve a |
|---|---|---|
| `tipo_habitacion` | PK `id_tipo`; `nombre` único; `capacidad_max` > 0; `tarifa_noche` > 0 | RF-02 (filtro por tipo), RF-04 (capacidad RN-02 y tarifa para el total) |
| `habitacion` | PK `id_habitacion`; `numero` único; FK `id_tipo`; `estado` | RF-02 (lista de libres), RF-04 (habitación asignada) |
| `huesped` | PK `id_huesped`; `nombre`; `documento` único | RF-04 (el huésped debe existir, RN-05) |
| `reserva` | PK `id_reserva`; FK `id_huesped`, `id_habitacion`; fechas; `numero_personas` > 0; tarifa; total; estado | RF-04 (escritura y lectura), RF-02 (determina ocupación) |

Relaciones: `tipo_habitacion 1—N habitacion`, `habitacion 1—N reserva`, `huesped 1—N reserva`.

**Cambios frente al modelo del segundo corte**

1. Se omite la tabla `usuario`: la autenticación quedó fuera del alcance en la plantilla del grupo.
2. Se agregan `CHECK` sobre los valores de `habitacion.estado` y `reserva.estado` (antes eran texto libre).
3. Se agregan `CHECK (tarifa_noche > 0)` y `CHECK (total > 0)` en `reserva`.
4. Se nombran las restricciones (`ck_reserva_fechas`, `ex_reserva_sin_solape`) para traducir errores con claridad.
5. Índices en `habitacion(id_tipo)` y `reserva(id_habitacion, fecha_entrada, fecha_salida)` para RNF-01.
6. Se mantiene `tipo_habitacion` aunque la plantilla nombraba solo tres tablas: la capacidad y la tarifa
   son del tipo, no de cada habitación (datos de dominio de la sección 1.2).
7. **Stack:** la persistencia se implementa en **Python 3.13 + psycopg 3 + PostgreSQL 16**, para continuar
   el backend FastAPI del repositorio en lugar de Spring Boot. Se conserva PostgreSQL por la restricción
   de exclusión sobre rangos de fechas, que era la razón principal de la elección del motor.

### 3.2 Base reproducible

| Archivo | Contenido |
|---|---|
| `db/01_schema.sql` | Esquema idempotente (borra y recrea las 4 tablas). |
| `db/02_seed.sql` | Estado inicial conocido. |
| `db/03_verificacion.sql` | Conteos esperados. |
| `scripts/reset_db.py` | Ejecuta 01 + 02 y muestra 03. Funciona en Windows y Linux, sin `psql`. |

**Estado inicial (fechas de referencia, diciembre de 2026):**

- Tipos: Estándar (cap. 2, $120 000), Familiar (cap. 4, $200 000), Suite (cap. 3, $280 000).
- 24 habitaciones: Estándar 101–112, Familiar 201–208, Suite 301–304.
- Huéspedes: 1 Ana Torres (1020304050), 2 Carlos Méndez (79888777), 3 Laura Smith (P12345678).
- Reservas:
  - id 1: Suite **301**, del 2026-12-20 al 2026-12-23, **CONFIRMADA** (casos de solape).
  - id 2: Suite **302**, mismas fechas, **CANCELADA** (comprueba que una reserva inactiva no bloquea).
  - id 3: Estándar **101**, del 2026-12-10 al 2026-12-12, **CONFIRMADA**.

Las fechas son futuras para cumplir RN-04. Si la entrega se reutiliza después de diciembre de 2026,
deben moverse en `02_seed.sql` y en las pruebas.

### 3.3 Acceso separado: repositorios y contrato para la semana 2

| Repositorio | Operación | Entrada → Resultado | Para qué |
|---|---|---|---|
| `PgTipoHabitacionRepository` | `buscar_por_id` | `id_tipo` → `TipoHabitacion \| None` | RF-02/RF-04: capacidad y tarifa |
| `PgHabitacionRepository` | `buscar_libres_por_tipo_y_rango` | `id_tipo, entrada, salida` → `list[Habitacion]` | RF-02 (respuesta) y RF-04 (asignar la de menor número) |
| | `buscar_por_tipo`, `obtener_por_id` | → `list[Habitacion]`, `Habitacion \| None` | Apoyo a RF-04 |
| `PgHuespedRepository` | `obtener_por_id` | `id_huesped` → `Huesped \| None` | RF-04: verificar existencia (RN-05) |
| `PgReservaRepository` | `buscar_reservas_solapadas` | `id_habitacion, entrada, salida` → `list[Reserva]` | RF-04: el hecho con el que negocio decide disponibilidad |
| | `guardar` | `NuevaReserva` → `int` (id real) | RF-04: persistir. Lanza `SolapeReservaError`, `ReferenciaInexistenteError` o `DatosInvalidosError` |
| | `buscar_por_id` | `id_reserva` → `Reserva \| None` | RF-04: confirmación; representa la ausencia con `None` |

- Contratos (protocolos) en `app/persistence/contracts.py`; objetos en `models.py`; errores en `errors.py`.
- **Transacción:** la abre y la cierra `unidad_de_trabajo()` (`app/persistence/db.py`). En la semana 2
  la usará el servicio `RegistrarReservaService`, que **confirma** si todo sale bien y **revierte** ante
  cualquier excepción. La conexión se cierra siempre en `finally`. Los repositorios no hacen commit.
- `guardar` usa un SAVEPOINT: si la base rechaza la habitación, la transacción sigue viva y el servicio
  puede reintentar con otra libre (algoritmo de asignación de la sección 10).
- **Separación:** el repositorio consulta y guarda; el servicio aplicará RN-01 a RN-05 en la semana 2;
  los endpoints y la pantalla no contienen SQL (verificado con `scripts/verificar_capas.py`).

> **Nota:** las rutas heredadas en `app/routes/` siguen usando MongoDB. En la semana 2 se reemplazan por
> los endpoints `GET /habitaciones/disponibilidad` y `POST /reservas`, que llamarán a los servicios.

---

## 4. Cómo repetir la verificación

### Requisitos

| Herramienta | Versión probada |
|---|---|
| Python | 3.13 (≥ 3.10) |
| PostgreSQL | 16 (instalación local o `docker compose`) |
| psycopg | 3.3.8 (`psycopg[binary]`) |
| pytest | 8.x |

### Pasos

```bash
# 1. Base de datos (elegir una opción)
docker compose up -d                       # opción A: contenedor PostgreSQL 16
# opción B: PostgreSQL local, como superusuario:
#   CREATE ROLE marea LOGIN PASSWORD 'marea_dev';
#   CREATE DATABASE marea_test OWNER marea;

# 2. Entorno Python (Windows: venv\Scripts\activate)
python -m venv venv
source venv/bin/activate
pip install -r requirements-persistencia.txt

# 3. Configuración (valores de ejemplo, sin credenciales reales)
cp .env.example .env                       # Windows: copy .env.example .env

# 4. Recrear la base con su estado inicial
python -m scripts.reset_db

# 5. Pruebas de integración contra PostgreSQL real
pytest -v tests/

# 6. Demostración por consola (guardar, releer desde conexión nueva, id inexistente, solape)
python -m scripts.reset_db
python -m scripts.demo_persistencia

# 7. Medición RNF-01 (carga 5 000 reservas, mide y restaura el estado inicial)
python -m scripts.medir_disponibilidad

# 8. Verificación RNF-06 (SQL solo en la capa de persistencia)
python -m scripts.verificar_capas
```

`btree_gist` es una extensión *trusted* desde PostgreSQL 13: el dueño de la base puede crearla sin
ser superusuario.

### Resultados esperados

- `reset_db`: Estándar 12, Familiar 8, Suite 4; 3 huéspedes; 2 reservas CONFIRMADA y 1 CANCELADA.
- `pytest`: **14 passed**.
- `demo_persistencia`:
  ```
  1) Suites libres 21-22 dic: ['302', '303', '304']
  2) Reserva guardada id=4 habitación=201 total=600000.00
  3) Recuperada desde conexión nueva: id=4 estado=CONFIRMADA 2026-12-20->2026-12-23 total=600000.00
  4) Reserva 999999: None
  5) Solape rechazado por la BD: La habitación ya tiene una reserva activa en ese rango
  ```
- `medir_disponibilidad`: `"cumple": true` (máximo ≤ 200 ms).
- `verificar_capas`: `OK ... (0 hallazgos)`.

### Evidencias (`evidencias/`)

| Archivo | Qué demuestra |
|---|---|
| `pytest_resultado.txt` | Las 14 pruebas de integración, cada una con su RF/RNF/CA |
| `demo_consola.txt` | Lectura, escritura y persistencia real desde una conexión nueva |
| `rnf01_tiempos.json` | 20 tiempos individuales, cantidad de reservas y entorno |
| `verificar_capas.txt` | 0 sentencias SQL fuera de la capa de persistencia |

---

## 5. Ficha RF–RNF del equipo

### RF-04 · Crear reserva (prioridad 1)

| Elemento | Respuesta del equipo |
|---|---|
| Identificador y enunciado | **RF-04.** El sistema creará una reserva CONFIRMADA para un huésped, con una habitación libre del tipo solicitado, calculando noches, tarifa por noche y total. Incluye los rechazos de RF-05: fechas inválidas, capacidad excedida o sin disponibilidad. |
| Actor y resultado esperado | Recepcionista. Obtiene el id real de la reserva, la habitación asignada, las fechas y el total; o un mensaje de rechazo claro. |
| Prioridad y justificación | **1.** Valor alto (tarea central y fuente de dobles reservas); relevancia arquitectónica alta (escritura transaccional, concurrencia, restricción de exclusión); concentra el riesgo R1, por eso va primero. Reutiliza la consulta de libres de RF-02. |
| RNF asociados | RNF-01, RNF-03, RNF-06, RNF-08 |
| ISO/IEC 25010:2023 | Eficiencia de desempeño / comportamiento temporal · Fiabilidad / tolerancia a fallos · Mantenibilidad / modularidad y capacidad para ser probado · Fiabilidad / ausencia de fallos |
| Condición, medida y umbral | RNF-01: API p95 ≤ 2 s con 10 usuarios y ≥ 5 000 reservas. RNF-03: 0 filas parciales ante fallo. RNF-06: 0 SQL fuera de persistencia; servicio probado con repositorio simulado (≥ 1 caso válido y ≥ 1 de rechazo). RNF-08: 10 solicitudes simultáneas → 1 reserva, 9 rechazos, 0 solapes. |
| Prueba, evidencia y semana | Sem 1: `test_rf04_*`, `test_integridad_*`, `test_rnf03_*`, `test_rnf08_*`, `demo_consola.txt`. Sem 2: servicio con repositorio simulado y medición en la API. Sem 3: CA-01, CA-03, CA-05 a CA-07 de extremo a extremo. |
| Datos y operaciones de persistencia | Tablas `reserva`, `habitacion`, `tipo_habitacion`, `huesped`. Operaciones `HuespedRepo.obtener_por_id`, `TipoHabitacionRepo.buscar_por_id`, `HabitacionRepo.buscar_libres_por_tipo_y_rango`, `ReservaRepo.buscar_reservas_solapadas`, `guardar`, `buscar_por_id`. |
| Resultado sem 1 y pendientes | ✔ Guardar y recuperar desde una conexión nueva; id inexistente → `None`; exclusión, CHECK de fechas y FK verificadas; atomicidad y reintento con SAVEPOINT; concurrencia 1/10. ☐ Pendiente sem 2: `RegistrarReservaService` con RN-01 a RN-05, cálculo del total, endpoint `POST /reservas`, pruebas con repositorio simulado. ☐ Sem 3: pantalla y flujo completo. |

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
| Datos y operaciones de persistencia | Tablas `habitacion`, `reserva`, `tipo_habitacion`. Operaciones `TipoHabitacionRepo.buscar_por_id` y `HabitacionRepo.buscar_libres_por_tipo_y_rango`. |
| Resultado sem 1 y pendientes | ✔ La 301 no aparece del 21 al 22; un rango contiguo no es solape; una reserva cancelada no bloquea; tipo sin reservas → 8 Familiares. RNF-01 (repositorio): máx. ≈ 2 ms con 5 003 reservas. ☐ Pendiente sem 2: validación de capacidad en el servicio y medición en la API. |

### Hallazgo durante las pruebas

La prueba de atomicidad (RNF-03) falló en la primera ejecución. El SAVEPOINT de `guardar` se convertía
en una transacción completa y confirmaba la fila cuando no había una transacción externa abierta. Se
corrigió en `unidad_de_trabajo()`, que ahora abre siempre una transacción explícita. Después de la
corrección, las 14 pruebas pasan de forma repetible.

---

### Antes de cerrar

Construiremos **RF-04 (crear reserva)** y **RF-02 (consultar disponibilidad)**, en ese orden, porque RF-04
concentra el valor y el riesgo de doble reserva, y comparte con RF-02 la consulta de habitaciones libres.
Esperamos respuestas rápidas (RNF-01), cero datos parciales (RNF-03), cero dobles reservas bajo
concurrencia (RNF-08) y capas separadas y fáciles de probar (RNF-06). Las pruebas de integración, la
salida de consola y las mediciones guardadas en `evidencias/` lo verifican. La semana 2 parte de estos
mismos contratos.
