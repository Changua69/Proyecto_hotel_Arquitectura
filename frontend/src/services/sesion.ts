// Sesión del usuario guardada por Login.tsx en localStorage ("user").
export type Rol = "huesped" | "recepcionista" | "admin"

export interface Sesion {
  email: string
  role: Rol
  token: string
}

export const ROLES_PERSONAL: Rol[] = ["recepcionista", "admin"]

export function leerSesion(): Sesion | null {
  try {
    const crudo = localStorage.getItem("user")
    if (!crudo) return null
    const s = JSON.parse(crudo)
    return s && s.token && s.role ? (s as Sesion) : null
  } catch {
    return null
  }
}

export function guardarSesion(s: Sesion): void {
  localStorage.setItem("user", JSON.stringify(s))
}

export function cerrarSesion(): void {
  localStorage.removeItem("user")
}

export const esPersonal = (s: Sesion | null) => !!s && ROLES_PERSONAL.includes(s.role)

export const NOMBRE_ROL: Record<Rol, string> = {
  huesped: "Huésped",
  recepcionista: "Recepción",
  admin: "Administración",
}

/** Página de inicio según el rol. */
export const inicioDe = (s: Sesion | null) => (esPersonal(s) ? "/panel" : "/dashboard")
