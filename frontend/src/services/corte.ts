import API from "./api"

// Contratos del corte vertical (semana 14): mismos nombres y fechas AAAA-MM-DD que el backend.
export interface HabitacionLibre { id_habitacion: number; numero: string }

export interface Disponibilidad {
  id_tipo: number
  tipo: string
  capacidad: number
  tarifa_noche: number
  fecha_entrada: string
  fecha_salida: string
  noches: number
  personas: number
  habitaciones_disponibles: HabitacionLibre[]
}

export interface ReservaEntrada {
  id_huesped: number
  id_tipo: number
  fecha_entrada: string
  fecha_salida: string
  numero_personas: number
}

export interface Reserva {
  id_reserva: number
  estado: string
  huesped: { id_huesped: number; nombre: string }
  habitacion: { id_habitacion: number; numero: string; tipo: string }
  fecha_entrada: string
  fecha_salida: string
  noches: number
  numero_personas: number
  tarifa_noche: number
  total: number
}

export const consultarDisponibilidad = (q: { id_tipo: number; fecha_entrada: string; fecha_salida: string; personas: number }, signal?: AbortSignal) =>
  API.get<Disponibilidad>("/api/disponibilidad", { params: q, signal }).then((r) => r.data)

export const crearReserva = (r: ReservaEntrada) => API.post<Reserva>("/api/reservas", r).then((x) => x.data)

export const consultarReserva = (id: number) => API.get<Reserva>(`/api/reservas/${id}`).then((r) => r.data)
