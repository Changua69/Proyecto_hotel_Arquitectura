import API from "./api"

// Contrato de /api/huespedes (mismos nombres que el backend).
export interface Huesped {
  id_huesped: number
  nombre: string
  documento: string
  nacionalidad: string | null
  telefono: string | null
  correo: string | null
}

export type HuespedEntrada = Omit<Huesped, "id_huesped">

/** Campos vacíos viajan como null (el backend los guarda como "sin dato"). */
const limpiar = (h: HuespedEntrada): HuespedEntrada => ({
  nombre: h.nombre.trim(),
  documento: h.documento.trim(),
  nacionalidad: h.nacionalidad?.trim() || null,
  telefono: h.telefono?.trim() || null,
  correo: h.correo?.trim() || null,
})

export const listarHuespedes = (buscar?: string, signal?: AbortSignal) =>
  API.get<Huesped[]>("/api/huespedes", { params: buscar ? { buscar } : {}, signal }).then((r) => r.data)

export const obtenerHuesped = (id: number) => API.get<Huesped>(`/api/huespedes/${id}`).then((r) => r.data)

export const miFicha = () => API.get<Huesped>("/api/huespedes/yo").then((r) => r.data)

/** Huésped con cuenta antigua (sin ficha): registra sus datos; el correo lo pone el backend. */
export const completarMiFicha = (d: { nombre: string; documento: string; telefono: string | null }) =>
  API.post<Huesped>("/api/huespedes/yo", { nombre: d.nombre.trim(), documento: d.documento.trim(), telefono: d.telefono?.trim() || null }).then((r) => r.data)

export const crearHuesped = (h: HuespedEntrada) => API.post<Huesped>("/api/huespedes", limpiar(h)).then((r) => r.data)

export const actualizarHuesped = (id: number, h: HuespedEntrada) =>
  API.put<Huesped>(`/api/huespedes/${id}`, limpiar(h)).then((r) => r.data)

export const eliminarHuesped = (id: number) => API.delete(`/api/huespedes/${id}`)
