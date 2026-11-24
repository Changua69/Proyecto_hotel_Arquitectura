import API from "./api"

export interface ReservaFila {
  id_reserva: number
  estado: "CONFIRMADA" | "EN_CURSO" | "FINALIZADA" | "CANCELADA"
  fecha_entrada: string
  fecha_salida: string
  noches: number
  numero_personas: number
  tarifa_noche: number
  total: number
  id_huesped: number
  huesped: string
  habitacion: string
  tipo: string
}

export interface Resumen {
  fecha: string
  huespedes: number
  habitaciones: number
  ocupadas_hoy: number
  ocupacion_pct: number
  reservas_activas: number
  llegadas_hoy: number
  ventas_mes: number
  reservas_mes: number
  proximas_llegadas: ReservaFila[]
}

export interface Linea { grupo: string; reservas: number; noches: number; total: number }

export interface Reporte {
  desde: string
  hasta: string
  generado: string
  total: number
  reservas_vendidas: number
  noches: number
  canceladas: number
  por_tipo: Linea[]
  por_estado: Linea[]
  reservas: ReservaFila[]
}

export interface Usuario { email: string; nombre: string; rol: "huesped" | "recepcionista" | "admin" }
export interface Tipo { id_tipo: number; nombre: string; capacidad_max: number; tarifa_noche: number }

export const resumenPanel = () => API.get<Resumen>("/api/panel/resumen").then((r) => r.data)

export const listarReservas = (f: { estado?: string; desde?: string; hasta?: string }) =>
  API.get<ReservaFila[]>("/api/reservas", { params: Object.fromEntries(Object.entries(f).filter(([, v]) => v)) }).then((r) => r.data)

export const cancelarReserva = (id: number) => API.post(`/api/reservas/${id}/cancelar`)
export const checkIn = (id: number) => API.post(`/api/reservas/${id}/checkin`)
export const checkOut = (id: number) => API.post(`/api/reservas/${id}/checkout`)

export const reporteVentas = (desde: string, hasta: string) =>
  API.get<Reporte>("/api/reportes/ventas", { params: { desde, hasta } }).then((r) => r.data)

/** Descarga el PDF: se pide como blob (con el token) y se guarda con el nombre que manda el backend. */
export async function descargarReportePdf(desde: string, hasta: string): Promise<string> {
  const r = await API.get<Blob>("/api/reportes/ventas.pdf", { params: { desde, hasta }, responseType: "blob" })
  const cabecera: string = r.headers["content-disposition"] || ""
  const nombre = /filename="([^"]+)"/.exec(cabecera)?.[1] || `reporte_ventas_${desde}_${hasta}.pdf`
  const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }))
  const a = document.createElement("a")
  a.href = url
  a.download = nombre
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  return nombre
}

export const listarUsuarios = () => API.get<Usuario[]>("/api/admin/usuarios").then((r) => r.data)
export const crearUsuario = (u: Usuario & { clave: string }) => API.post<Usuario>("/api/admin/usuarios", u).then((r) => r.data)
export const cambiarRol = (email: string, rol: string) =>
  API.put<Usuario>(`/api/admin/usuarios/${encodeURIComponent(email)}/rol`, { rol }).then((r) => r.data)
export const eliminarUsuario = (email: string) => API.delete(`/api/admin/usuarios/${encodeURIComponent(email)}`)

export const listarTipos = () => API.get<Tipo[]>("/api/admin/tipos").then((r) => r.data)
export const actualizarTipo = (id: number, capacidad_max: number, tarifa_noche: number) =>
  API.put<Tipo>(`/api/admin/tipos/${id}`, { capacidad_max, tarifa_noche }).then((r) => r.data)
