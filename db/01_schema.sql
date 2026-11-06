-- =====================================================================
-- MareaDorada Pro v1.0 - Corte vertical "Crear una reserva"
-- Semana 13: esquema mínimo para RF-02 (disponibilidad) y RF-04 (reserva)
-- Motor: PostgreSQL 16
-- El script es idempotente: borra y recrea las tablas del corte.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS btree_gist;

DROP TABLE IF EXISTS reserva          CASCADE;
DROP TABLE IF EXISTS huesped          CASCADE;
DROP TABLE IF EXISTS habitacion       CASCADE;
DROP TABLE IF EXISTS tipo_habitacion  CASCADE;

-- Catálogo de tipos: aporta capacidad (RN-02) y tarifa (cálculo del total).
CREATE TABLE tipo_habitacion (
    id_tipo        SERIAL        PRIMARY KEY,
    nombre         VARCHAR(30)   NOT NULL UNIQUE,
    capacidad_max  INT           NOT NULL CHECK (capacidad_max > 0),
    tarifa_noche   NUMERIC(12,2) NOT NULL CHECK (tarifa_noche > 0)
);

-- Habitaciones físicas del resort (24).
CREATE TABLE habitacion (
    id_habitacion  SERIAL        PRIMARY KEY,
    numero         VARCHAR(10)   NOT NULL UNIQUE,
    id_tipo        INT           NOT NULL REFERENCES tipo_habitacion(id_tipo),
    estado         VARCHAR(15)   NOT NULL DEFAULT 'LIBRE'
                   CHECK (estado IN ('LIBRE','RESERVADA','OCUPADA','EN_LIMPIEZA'))
);

-- Huéspedes. En el corte solo se consultan por id (RF-04).
CREATE TABLE huesped (
    id_huesped     SERIAL        PRIMARY KEY,
    nombre         VARCHAR(100)  NOT NULL,
    documento      VARCHAR(30)   NOT NULL UNIQUE,
    nacionalidad   VARCHAR(50),
    telefono       VARCHAR(20),
    correo         VARCHAR(120)
);

-- Reservas. La restricción de exclusión refuerza RN-01 en la base de datos:
-- dos reservas activas de la misma habitación no pueden solaparse,
-- incluso ante solicitudes simultáneas. Rango semiabierto [entrada, salida).
CREATE TABLE reserva (
    id_reserva       SERIAL        PRIMARY KEY,
    id_huesped       INT           NOT NULL REFERENCES huesped(id_huesped),
    id_habitacion    INT           NOT NULL REFERENCES habitacion(id_habitacion),
    fecha_entrada    DATE          NOT NULL,
    fecha_salida     DATE          NOT NULL,
    numero_personas  INT           NOT NULL CHECK (numero_personas > 0),
    tarifa_noche     NUMERIC(12,2) NOT NULL CHECK (tarifa_noche > 0),
    total            NUMERIC(12,2) NOT NULL CHECK (total > 0),
    estado           VARCHAR(15)   NOT NULL DEFAULT 'CONFIRMADA'
                     CHECK (estado IN ('CONFIRMADA','EN_CURSO','FINALIZADA','CANCELADA')),
    creada_en        TIMESTAMP     NOT NULL DEFAULT now(),
    CONSTRAINT ck_reserva_fechas CHECK (fecha_salida > fecha_entrada),
    CONSTRAINT ex_reserva_sin_solape EXCLUDE USING gist (
        id_habitacion WITH =,
        daterange(fecha_entrada, fecha_salida, '[)') WITH &&
    ) WHERE (estado IN ('CONFIRMADA','EN_CURSO'))
);

CREATE INDEX ix_habitacion_tipo ON habitacion(id_tipo);
CREATE INDEX ix_reserva_habitacion_fechas ON reserva(id_habitacion, fecha_entrada, fecha_salida);
