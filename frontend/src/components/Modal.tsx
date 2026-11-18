import { useEffect, useId, useRef } from "react"
import type { ReactNode } from "react"
import { createPortal } from "react-dom"
import "../styles/app.css"

/*
 * Ventana emergente reutilizable (semana 15).
 *
 * Problemas que resuelve:
 * - Superposición: se dibuja con un portal en <body>, fuera de tarjetas con overflow/transform/z-index
 *   que la recortaban o la dejaban detrás de otros elementos. Las ventanas abiertas forman una pila:
 *   la más reciente queda encima (z-index creciente) y solo ella responde a Esc y al clic fuera.
 * - Apertura/cierre: se abre y se cierra solo con la prop `abierto`; cierra con la X, con Esc o con
 *   clic en el fondo (solo si el clic EMPIEZA y TERMINA en el fondo, así seleccionar texto y soltar
 *   afuera no la cierra). Con `bloqueado` (p. ej. mientras dice "Guardando...") no se puede cerrar.
 * - Scroll: la página de atrás no se desplaza mientras haya una ventana abierta, y se restaura al cerrar
 *   la última.
 * - Foco: entra a la ventana, Tab no se escapa de ella y al cerrar vuelve al botón que la abrió.
 * - Diseño: tamaño máximo con scroll interno; en celular ocupa el ancho disponible.
 */

const pila: string[] = []
let overflowAnterior = ""
let paddingAnterior = ""

function bloquearScroll() {
  if (pila.length !== 1) return
  const barra = window.innerWidth - document.documentElement.clientWidth
  overflowAnterior = document.body.style.overflow
  paddingAnterior = document.body.style.paddingRight
  document.body.style.overflow = "hidden"
  if (barra > 0) document.body.style.paddingRight = `${barra}px` // evita el "salto" del contenido
}

function liberarScroll() {
  if (pila.length !== 0) return
  document.body.style.overflow = overflowAnterior
  document.body.style.paddingRight = paddingAnterior
}

const ENFOCABLES =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export interface ModalProps {
  abierto: boolean
  titulo: ReactNode
  onCerrar: () => void
  children: ReactNode
  /** Botones de abajo (Cancelar / Guardar). */
  pie?: ReactNode
  descripcion?: ReactNode
  tamano?: "sm" | "md" | "lg"
  /** Impide cerrar (Esc, fondo, X) mientras hay una operación en curso. */
  bloqueado?: boolean
}

export default function Modal({ abierto, titulo, onCerrar, children, pie, descripcion, tamano = "md", bloqueado = false }: ModalProps) {
  const id = useId()
  const ventana = useRef<HTMLDivElement>(null)
  const inicioClicEnFondo = useRef(false)
  // Valores actuales sin volver a registrar los manejadores en cada render.
  const cerrarRef = useRef(onCerrar)
  const bloqueadoRef = useRef(bloqueado)
  useEffect(() => {
    cerrarRef.current = onCerrar
    bloqueadoRef.current = bloqueado
  })

  useEffect(() => {
    if (!abierto) return
    const anterior = document.activeElement as HTMLElement | null
    pila.push(id)
    bloquearScroll()

    // Foco inicial: un campo con data-autofocus, o el primer elemento enfocable, o la ventana.
    const t = window.setTimeout(() => {
      const v = ventana.current
      if (!v) return
      const objetivo = v.querySelector<HTMLElement>("[data-autofocus]") ||
        v.querySelector(".md-cuerpo")?.querySelector<HTMLElement>(ENFOCABLES) || v
      objetivo.focus()
    }, 0)

    const alTeclear = (e: KeyboardEvent) => {
      if (pila[pila.length - 1] !== id) return // solo la ventana de arriba
      if (e.key === "Escape") {
        e.stopPropagation()
        if (!bloqueadoRef.current) cerrarRef.current()
      } else if (e.key === "Tab" && ventana.current) {
        const elems = Array.from(ventana.current.querySelectorAll<HTMLElement>(ENFOCABLES))
          .filter((el) => el.offsetParent !== null)
        if (elems.length === 0) { e.preventDefault(); return }
        const primero = elems[0], ultimo = elems[elems.length - 1]
        if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus() }
        else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus() }
      }
    }
    document.addEventListener("keydown", alTeclear)

    return () => {
      window.clearTimeout(t)
      document.removeEventListener("keydown", alTeclear)
      const i = pila.lastIndexOf(id)
      if (i >= 0) pila.splice(i, 1)
      liberarScroll()
      if (anterior && document.contains(anterior)) anterior.focus()
    }
  }, [abierto, id])

  if (!abierto) return null
  // Posición en la pila: antes de registrarse (primer render) va encima de las que ya están abiertas.
  const posicion = pila.indexOf(id)
  const nivel = posicion >= 0 ? posicion : pila.length

  return createPortal(
    <div
      className="md-fondo"
      style={{ zIndex: 1000 + nivel * 10 }}
      onMouseDown={(e) => { inicioClicEnFondo.current = e.target === e.currentTarget }}
      onClick={(e) => {
        if (inicioClicEnFondo.current && e.target === e.currentTarget && !bloqueado) onCerrar()
        inicioClicEnFondo.current = false
      }}
    >
      <div
        ref={ventana}
        className={`md-ventana md-${tamano}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-titulo`}
        aria-describedby={descripcion ? `${id}-desc` : undefined}
        aria-busy={bloqueado || undefined}
        tabIndex={-1}
      >
        <header className="md-cabecera">
          <div>
            <h2 id={`${id}-titulo`} className="md-titulo">{titulo}</h2>
            {descripcion && <p id={`${id}-desc`} className="md-descripcion">{descripcion}</p>}
          </div>
          <button type="button" className="md-cerrar" onClick={onCerrar} disabled={bloqueado} aria-label="Cerrar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </header>
        <div className="md-cuerpo">{children}</div>
        {pie && <footer className="md-pie">{pie}</footer>}
      </div>
    </div>,
    document.body,
  )
}
