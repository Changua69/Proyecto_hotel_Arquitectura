import { useEffect } from "react"
import type { ReactNode } from "react"
import { Navigate, useNavigate } from "react-router-dom"
import toast from "react-hot-toast"
import { inicioDe, leerSesion } from "../services/sesion"
import type { Rol } from "../services/sesion"

/*
 * Protege una ruta de la interfaz según el rol. Es solo comodidad para el usuario:
 * el permiso real lo valida el backend en cada petición (401/403).
 */
export default function RequireRole({ roles, children }: { roles: Rol[]; children: ReactNode }) {
  const sesion = leerSesion()
  const navigate = useNavigate()

  // Si el backend responde 401 (sesión vencida), api.ts cierra la sesión y avisa con este evento.
  useEffect(() => {
    const alVencer = () => {
      toast.error("Su sesión venció. Inicie sesión de nuevo.", { id: "sesion-vencida" })
      navigate("/", { replace: true })
    }
    window.addEventListener("sesion-vencida", alVencer)
    return () => window.removeEventListener("sesion-vencida", alVencer)
  }, [navigate])

  if (!sesion) return <Navigate to="/" replace />
  if (!roles.includes(sesion.role)) return <Navigate to={inicioDe(sesion)} replace />
  return <>{children}</>
}
