-- Verificación rápida del estado inicial (ejecutar después de 01 y 02).
-- Resultado esperado: Estándar 12, Familiar 8, Suite 4, 3 huéspedes, 3 reservas (2 activas).
SELECT t.nombre, count(*) AS habitaciones
FROM habitacion h JOIN tipo_habitacion t USING (id_tipo)
GROUP BY t.nombre ORDER BY t.nombre;

SELECT count(*) AS huespedes FROM huesped;

SELECT estado, count(*) AS reservas FROM reserva GROUP BY estado ORDER BY estado;
