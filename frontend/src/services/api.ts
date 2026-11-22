import axios from "axios"
import { cerrarSesion, leerSesion } from "./sesion"

const apiUrl = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")

const API = axios.create({
  baseURL: apiUrl,
  timeout: 20000,
})

// Cada petición lleva el token de la sesión (el backend decide los permisos por rol).
API.interceptors.request.use((config) => {
  const sesion = leerSesion()
  if (sesion?.token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${sesion.token}`
  }
  return config
})

// Si el backend dice que la sesión venció (401 en una ruta /api), se cierra y se vuelve al login.
API.interceptors.response.use(
  (r) => r,
  (error) => {
    const url: string = error.config?.url || ""
    if (error.response?.status === 401 && url.startsWith("/api") && leerSesion()) {
      cerrarSesion()
      window.dispatchEvent(new Event("sesion-vencida"))
    }
    return Promise.reject(error)
  },
)

/** Error del backend clasificado para mostrarlo en pantalla. */
export interface ErrorApi {
  tipo: "red" | "validacion" | "no_encontrado" | "conflicto" | "permiso" | "sesion" | "servidor" | "otro"
  http: number | null
  codigo: string | null
  mensaje: string
  /** Errores por campo: { documento: "es obligatorio" } */
  campos: Record<string, string>
}

/**
 * Traduce cualquier fallo de axios a un mensaje comprensible.
 * Nunca devuelve un "éxito": quien lo llama decide qué ocultar o conservar.
 */
export function describirError(err: unknown): ErrorApi {
  if (!axios.isAxiosError(err)) {
    return { tipo: "otro", http: null, codigo: null, mensaje: "Ocurrió un error inesperado en la pantalla.", campos: {} }
  }
  if (!err.response) {
    const mensaje = err.code === "ECONNABORTED"
      ? "El servidor tardó demasiado en responder. Intente de nuevo."
      : "No se pudo conectar con el servidor. Verifique que el backend esté encendido e intente de nuevo."
    return { tipo: "red", http: null, codigo: "SIN_CONEXION", mensaje, campos: {} }
  }
  const http = err.response.status
  const cuerpo = (err.response.data ?? {}) as {
    detail?: unknown; codigo?: string; campo?: string; errores?: { campo: string; mensaje: string }[]
  }
  const campos: Record<string, string> = {}
  for (const e of cuerpo.errores ?? []) campos[e.campo] = e.mensaje
  const detalle = typeof cuerpo.detail === "string" ? cuerpo.detail : null
  if (cuerpo.campo && detalle) campos[cuerpo.campo] = detalle

  const tipo: ErrorApi["tipo"] =
    http === 400 || http === 422 ? "validacion"
      : http === 404 ? "no_encontrado"
      : http === 409 ? "conflicto"
      : http === 401 ? "sesion"
      : http === 403 ? "permiso"
      : http >= 500 ? "servidor"
      : "otro"

  const porDefecto: Record<ErrorApi["tipo"], string> = {
    validacion: "Revise los datos del formulario.",
    no_encontrado: "El registro no existe.",
    conflicto: "La operación entra en conflicto con datos existentes.",
    sesion: "Su sesión venció. Inicie sesión de nuevo.",
    permiso: "Su rol no tiene permiso para esta operación.",
    servidor: "El servidor tuvo un problema. Intente de nuevo más tarde.",
    red: "", otro: "No fue posible completar la operación.",
  }
  return { tipo, http, codigo: cuerpo.codigo ?? null, mensaje: detalle || porDefecto[tipo], campos }
}

export default API
