-- =====================================================================
-- Datos de prueba con estado inicial conocido (semana 13).
-- Fechas de referencia: diciembre de 2026 (futuras, cumplen RN-04).
-- Mantener estos datos como referencia en las semanas 2 y 3.
-- =====================================================================

-- Tipos (tarifas de ejemplo; deben confirmarse con el Resort)
INSERT INTO tipo_habitacion (id_tipo, nombre, capacidad_max, tarifa_noche) VALUES
    (1, 'Estándar', 2, 120000),
    (2, 'Familiar', 4, 200000),
    (3, 'Suite',    3, 280000);

-- 24 habitaciones: Estándar 101-112, Familiar 201-208, Suite 301-304
INSERT INTO habitacion (numero, id_tipo)
SELECT (100 + n)::text, 1 FROM generate_series(1, 12) AS n;
INSERT INTO habitacion (numero, id_tipo)
SELECT (200 + n)::text, 2 FROM generate_series(1, 8) AS n;
INSERT INTO habitacion (numero, id_tipo)
SELECT (300 + n)::text, 3 FROM generate_series(1, 4) AS n;

-- Tres huéspedes de ejemplo
INSERT INTO huesped (id_huesped, nombre, documento, nacionalidad, telefono, correo) VALUES
    (1, 'Ana Torres',    '1020304050', 'Colombiana', '3001234567', 'ana@example.com'),
    (2, 'Carlos Méndez', '79888777',   'Colombiana', '3109876543', 'carlos@example.com'),
    (3, 'Laura Smith',   'P12345678',  'Estadounidense', '3205551234', 'laura@example.com');

-- Reservas preexistentes para probar solapes
--  R1: Suite 301 ocupada del 20 al 23 de diciembre (CONFIRMADA)  -> CA-02, CA-04
--  R2: Suite 302 mismas fechas pero CANCELADA (no bloquea)        -> reserva inactiva
--  R3: Estándar 101 del 10 al 12 de diciembre (CONFIRMADA)
INSERT INTO reserva (id_reserva, id_huesped, id_habitacion, fecha_entrada, fecha_salida,
                     numero_personas, tarifa_noche, total, estado) VALUES
    (1, 1, (SELECT id_habitacion FROM habitacion WHERE numero = '301'),
        DATE '2026-12-20', DATE '2026-12-23', 2, 280000, 840000, 'CONFIRMADA'),
    (2, 2, (SELECT id_habitacion FROM habitacion WHERE numero = '302'),
        DATE '2026-12-20', DATE '2026-12-23', 2, 280000, 840000, 'CANCELADA'),
    (3, 3, (SELECT id_habitacion FROM habitacion WHERE numero = '101'),
        DATE '2026-12-10', DATE '2026-12-12', 1, 120000, 240000, 'CONFIRMADA');

-- Ajustar secuencias tras insertar ids explícitos
SELECT setval('tipo_habitacion_id_tipo_seq', (SELECT max(id_tipo) FROM tipo_habitacion));
SELECT setval('huesped_id_huesped_seq',      (SELECT max(id_huesped) FROM huesped));
SELECT setval('reserva_id_reserva_seq',      (SELECT max(id_reserva) FROM reserva));
