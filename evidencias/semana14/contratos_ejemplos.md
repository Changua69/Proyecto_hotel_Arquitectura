# Ejemplos de contrato ejecutados contra el backend (semana 14)
Generado con `python -m scripts.demo_api` sobre la base de prueba recién creada.

## RF-02 válido (CA-02): Suites libres del 21 al 22 de diciembre

```http
GET /api/disponibilidad?id_tipo=3&fecha_entrada=2026-12-21&fecha_salida=2026-12-22&personas=2
```

```http
HTTP 200 OK

{
  "id_tipo": 3,
  "tipo": "Suite",
  "capacidad": 3,
  "tarifa_noche": 280000,
  "fecha_entrada": "2026-12-21",
  "fecha_salida": "2026-12-22",
  "noches": 1,
  "personas": 2,
  "habitaciones_disponibles": [
    {
      "id_habitacion": 22,
      "numero": "302"
    },
    {
      "id_habitacion": 23,
      "numero": "303"
    },
    {
      "id_habitacion": 24,
      "numero": "304"
    }
  ]
}
```

## RF-02 capacidad excedida (CA-05)

```http
GET /api/disponibilidad?id_tipo=1&fecha_entrada=2026-12-20&fecha_salida=2026-12-23&personas=3
```

```http
HTTP 422 Unprocessable Entity

{
  "detail": "El tipo Estándar admite como máximo 2 personas.",
  "codigo": "CAPACIDAD_EXCEDIDA"
}
```

## RF-04 válido (CA-01): Familiar para 3 personas del 20 al 23 de diciembre

```http
POST /api/reservas
Content-Type: application/json

{
  "id_huesped": 1,
  "id_tipo": 2,
  "fecha_entrada": "2026-12-20",
  "fecha_salida": "2026-12-23",
  "numero_personas": 3
}
```

```http
HTTP 201 Created
Location: /api/reservas/4

{
  "id_reserva": 4,
  "estado": "CONFIRMADA",
  "huesped": {
    "id_huesped": 1,
    "nombre": "Ana Torres"
  },
  "habitacion": {
    "id_habitacion": 13,
    "numero": "201",
    "tipo": "Familiar"
  },
  "fecha_entrada": "2026-12-20",
  "fecha_salida": "2026-12-23",
  "noches": 3,
  "numero_personas": 3,
  "tarifa_noche": 200000,
  "total": 600000
}
```

## RF-04 confirmación: consultar la reserva creada

```http
GET /api/reservas/4
```

```http
HTTP 200 OK

{
  "id_reserva": 4,
  "estado": "CONFIRMADA",
  "huesped": {
    "id_huesped": 1,
    "nombre": "Ana Torres"
  },
  "habitacion": {
    "id_habitacion": 13,
    "numero": "201",
    "tipo": "Familiar"
  },
  "fecha_entrada": "2026-12-20",
  "fecha_salida": "2026-12-23",
  "noches": 3,
  "numero_personas": 3,
  "tarifa_noche": 200000,
  "total": 600000
}
```

## RF-04 reserva inexistente

```http
GET /api/reservas/999999
```

```http
HTTP 404 Not Found

{
  "detail": "La reserva no existe.",
  "codigo": "NO_ENCONTRADO"
}
```

## RF-04 id inválido

```http
GET /api/reservas/abc
```

```http
HTTP 400 Bad Request

{
  "detail": "Datos de entrada inválidos. id_reserva: debe ser un número entero",
  "codigo": "DATOS_INVALIDOS",
  "errores": [
    {
      "campo": "id_reserva",
      "mensaje": "debe ser un número entero"
    }
  ]
}
```

## RF-04 fechas inválidas (CA-06)

```http
POST /api/reservas
Content-Type: application/json

{
  "id_huesped": 1,
  "id_tipo": 2,
  "fecha_entrada": "2026-12-23",
  "fecha_salida": "2026-12-20",
  "numero_personas": 2
}
```

```http
HTTP 400 Bad Request

{
  "detail": "La fecha de salida debe ser posterior a la de entrada.",
  "codigo": "FECHAS_INVALIDAS"
}
```

## RF-04 huésped inexistente

```http
POST /api/reservas
Content-Type: application/json

{
  "id_huesped": 999,
  "id_tipo": 2,
  "fecha_entrada": "2026-12-20",
  "fecha_salida": "2026-12-23",
  "numero_personas": 2
}
```

```http
HTTP 404 Not Found

{
  "detail": "El huésped no existe.",
  "codigo": "NO_ENCONTRADO"
}
```

## RF-04 campo obligatorio ausente

```http
POST /api/reservas
Content-Type: application/json

{
  "id_tipo": 2,
  "fecha_entrada": "2026-12-20",
  "fecha_salida": "2026-12-23",
  "numero_personas": 2
}
```

```http
HTTP 400 Bad Request

{
  "detail": "Datos de entrada inválidos. id_huesped: es obligatorio",
  "codigo": "DATOS_INVALIDOS",
  "errores": [
    {
      "campo": "id_huesped",
      "mensaje": "es obligatorio"
    }
  ]
}
```

## RF-04 sin disponibilidad (CA-03): se ocupan 302, 303 y 304 y se pide otra Suite

```http
POST /api/reservas
Content-Type: application/json

{
  "id_huesped": 2,
  "id_tipo": 3,
  "fecha_entrada": "2026-12-21",
  "fecha_salida": "2026-12-22",
  "numero_personas": 2
}
```

```http
HTTP 409 Conflict

{
  "detail": "No hay habitaciones disponibles para esas fechas.",
  "codigo": "SIN_DISPONIBILIDAD"
}
```
