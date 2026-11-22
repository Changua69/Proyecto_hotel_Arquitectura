import type { ReactNode } from "react"
import { NavLink, useNavigate } from "react-router-dom"
import logo from "../assets/image.ico"
import { cerrarSesion, leerSesion, NOMBRE_ROL } from "../services/sesion"
import type { Rol } from "../services/sesion"
import "../styles/app.css"

/* Estructura base de las pantallas del personal (dashboard general y CRUDs). */

interface Enlace { a: string; texto: string; roles: Rol[]; icono: ReactNode }

const i = (d: ReactNode) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">{d}</svg>
)

const ENLACES: Enlace[] = [
  { a: "/panel", texto: "Inicio", roles: ["recepcionista", "admin"], icono: i(<><rect x="3" y="3" width="7" height="9" /><rect x="14" y="3" width="7" height="5" /><rect x="14" y="12" width="7" height="9" /><rect x="3" y="16" width="7" height="5" /></>) },
  { a: "/panel/nueva-reserva", texto: "Nueva reserva", roles: ["recepcionista", "admin"], icono: i(<><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18M12 14v4M10 16h4" /></>) },
  { a: "/panel/huespedes", texto: "Huéspedes", roles: ["recepcionista", "admin"], icono: i(<><circle cx="9" cy="8" r="4" /><path d="M2 21c0-4 3-7 7-7s7 3 7 7M16 4a4 4 0 0 1 0 8M22 21c0-3-2-5.5-4.5-6.5" /></>) },
  { a: "/panel/reservas", texto: "Reservas", roles: ["recepcionista", "admin"], icono: i(<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />) },
  { a: "/panel/admin", texto: "Administración", roles: ["admin"], icono: i(<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>) },
]

export default function StaffLayout({ titulo, subtitulo, acciones, children }: {
  titulo: string; subtitulo?: string; acciones?: ReactNode; children: ReactNode
}) {
  const sesion = leerSesion()
  const navigate = useNavigate()
  const visibles = ENLACES.filter((e) => sesion && e.roles.includes(sesion.role))

  return (
    <div className="panel">
      <aside className="panel-lateral" aria-label="Menú del personal">
        <div className="panel-marca">
          <img src={logo} alt="" />
          <div><b>Marea Dorada</b><small>Panel del personal</small></div>
        </div>
        <nav style={{ display: "contents" }}>
          {visibles.map((e) => (
            <NavLink key={e.a} to={e.a} end className={({ isActive }) => `panel-enlace${isActive ? " activo" : ""}`}>
              {e.icono}<span>{e.texto}</span>
            </NavLink>
          ))}
        </nav>
        <div className="panel-usuario">
          <div className="correo">{sesion?.email}</div>
          <div className="rol" style={{ color: "var(--texto-3)", margin: "2px 0 10px" }}>{sesion ? NOMBRE_ROL[sesion.role] : ""}</div>
          <button className="btn btn-sec btn-chico" onClick={() => { cerrarSesion(); navigate("/") }}>Salir</button>
        </div>
      </aside>
      <main className="panel-contenido">
        <div className="panel-cabecera">
          <div>
            <h1>{titulo}</h1>
            {subtitulo && <p>{subtitulo}</p>}
          </div>
          {acciones}
        </div>
        {children}
      </main>
    </div>
  )
}
