import { useCallback, useEffect, useRef, useState } from "react"
import type { FormEvent } from "react"
import toast from "react-hot-toast"
import StaffLayout from "../components/StaffLayout"
import Modal from "../components/Modal"
import ConfirmDialog from "../components/ConfirmDialog"
import { describirError } from "../services/api"
import type { ErrorApi } from "../services/api"
import {
  actualizarHuesped, crearHuesped, eliminarHuesped, listarHuespedes, obtenerHuesped,
} from "../services/huespedes"
import type { Huesped, HuespedEntrada } from "../services/huespedes"
import { leerSesion } from "../services/sesion"

/*
 * CRUD de huéspedes (semana 15).
 * Interfaz -> GET/POST/PUT/DELETE /api/huespedes -> servicio -> repositorio -> MongoDB.
 *
 * Estados que se muestran en cada operación:
 *  inicial · en curso ("Cargando...", "Guardando...", "Eliminando...") · resultado ("Huésped #N guardado") · error.
 * Reglas: no hay "falsos éxitos" (el aviso de éxito sale solo con 200/201/204), un error oculta los
 * datos de la consulta anterior, los campos escritos se conservan si el guardado falla y el botón
 * se desactiva mientras se envía (sin dobles envíos).
 */

type Carga<T> =
  | { estado: "cargando" }
  | { estado: "listo"; datos: T }
  | { estado: "error"; error: ErrorApi }

const VACIO: HuespedEntrada = { nombre: "", documento: "", nacionalidad: "", telefono: "", correo: "" }

const CAMPOS: { k: keyof HuespedEntrada; etiqueta: string; req?: boolean; tipo?: string; ayuda?: string; ancho?: boolean; max: number }[] = [
  { k: "nombre", etiqueta: "Nombre completo", req: true, ancho: true, max: 100 },
  { k: "documento", etiqueta: "Documento", req: true, ayuda: "Letras, números, puntos o guiones", max: 30 },
  { k: "nacionalidad", etiqueta: "Nacionalidad", max: 50 },
  { k: "telefono", etiqueta: "Teléfono", tipo: "tel", ayuda: "7 a 20 dígitos", max: 20 },
  { k: "correo", etiqueta: "Correo", tipo: "email", ayuda: "Si el huésped tiene cuenta, debe ser el mismo correo", max: 120 },
]

/** Validación mínima en la pantalla (el backend vuelve a validar todo). */
function validarLocal(v: HuespedEntrada): Record<string, string> {
  const e: Record<string, string> = {}
  if (!v.nombre.trim()) e.nombre = "es obligatorio"
  else if (v.nombre.trim().length < 2) e.nombre = "debe tener al menos 2 caracteres"
  if (!v.documento.trim()) e.documento = "es obligatorio"
  const correo = v.correo?.trim()
  if (correo && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(correo)) e.correo = "no tiene un formato válido"
  return e
}

export default function Huespedes() {
  const sesion = leerSesion()
  const esAdmin = sesion?.role === "admin"

  // ------------------------------------------------------------ listado y búsqueda
  const [buscar, setBuscar] = useState("")
  const [lista, setLista] = useState<Carga<Huesped[]>>({ estado: "cargando" })
  const peticion = useRef<AbortController | null>(null)

  const cargar = useCallback(async (texto: string) => {
    peticion.current?.abort() // si había otra búsqueda en curso, se descarta su respuesta
    const ctrl = new AbortController()
    peticion.current = ctrl
    setLista({ estado: "cargando" }) // no se deja visible el resultado anterior mientras se busca
    try {
      const datos = await listarHuespedes(texto.trim() || undefined, ctrl.signal)
      if (!ctrl.signal.aborted) setLista({ estado: "listo", datos })
    } catch (err) {
      if (ctrl.signal.aborted) return
      setLista({ estado: "error", error: describirError(err) })
    }
  }, [])

  useEffect(() => {
    const t = window.setTimeout(() => cargar(buscar), buscar ? 300 : 0)
    return () => window.clearTimeout(t)
  }, [buscar, cargar])
  useEffect(() => () => peticion.current?.abort(), [])

  // ------------------------------------------------------------ formulario (crear / editar)
  const [form, setForm] = useState<{ abierto: boolean; id: number | null }>({ abierto: false, id: null })
  const [valores, setValores] = useState<HuespedEntrada>(VACIO)
  const [erroresCampo, setErroresCampo] = useState<Record<string, string>>({})
  const [errorForm, setErrorForm] = useState<ErrorApi | null>(null)
  const [guardando, setGuardando] = useState(false)

  const abrirCrear = () => {
    setValores(VACIO); setErroresCampo({}); setErrorForm(null)
    setForm({ abierto: true, id: null })
  }
  const abrirEditar = (h: Huesped) => {
    setValores({ nombre: h.nombre, documento: h.documento, nacionalidad: h.nacionalidad ?? "",
      telefono: h.telefono ?? "", correo: h.correo ?? "" })
    setErroresCampo({}); setErrorForm(null)
    setForm({ abierto: true, id: h.id_huesped })
  }
  const cerrarForm = () => { if (!guardando) setForm({ abierto: false, id: null }) }

  const cambiar = (k: keyof HuespedEntrada, valor: string) => {
    setValores((v) => ({ ...v, [k]: valor }))
    if (erroresCampo[k]) setErroresCampo((prev) => { const copia = { ...prev }; delete copia[k]; return copia })
  }

  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    if (guardando) return // evita el doble envío (Enter + clic)
    const locales = validarLocal(valores)
    setErroresCampo(locales)
    setErrorForm(null)
    if (Object.keys(locales).length) return

    setGuardando(true)
    try {
      const h = form.id === null ? await crearHuesped(valores) : await actualizarHuesped(form.id, valores)
      // Éxito confirmado por el backend (201 o 200): solo ahora se informa y se cierra.
      toast.success(form.id === null ? `Huésped #${h.id_huesped} registrado` : `Huésped #${h.id_huesped} actualizado`)
      setForm({ abierto: false, id: null })
      cargar(buscar)
    } catch (err) {
      const info = describirError(err)
      setErrorForm(info)               // los valores escritos se conservan para corregir y reintentar
      setErroresCampo(info.campos)
      if (info.tipo === "no_encontrado") cargar(buscar) // otro usuario lo eliminó: se refresca la lista
    } finally {
      setGuardando(false)
    }
  }

  // ------------------------------------------------------------ detalle / consulta por id
  const [idConsulta, setIdConsulta] = useState("")
  const [detalle, setDetalle] = useState<{ abierto: boolean; carga: Carga<Huesped> | null }>({ abierto: false, carga: null })

  const verDetalle = async (id: number) => {
    setDetalle({ abierto: true, carga: { estado: "cargando" } }) // se borra lo consultado antes
    try {
      setDetalle({ abierto: true, carga: { estado: "listo", datos: await obtenerHuesped(id) } })
    } catch (err) {
      setDetalle({ abierto: true, carga: { estado: "error", error: describirError(err) } })
    }
  }
  const consultarPorId = (e: FormEvent) => {
    e.preventDefault()
    const id = Number(idConsulta)
    if (!Number.isInteger(id) || id <= 0) {
      toast.error("Escriba un id de huésped válido (entero positivo).")
      return
    }
    verDetalle(id)
  }

  // ------------------------------------------------------------ eliminar
  const [borrar, setBorrar] = useState<Huesped | null>(null)
  const [eliminando, setEliminando] = useState(false)
  const [errorBorrar, setErrorBorrar] = useState<string | null>(null)

  const confirmarBorrado = async () => {
    if (!borrar || eliminando) return
    setEliminando(true); setErrorBorrar(null)
    try {
      await eliminarHuesped(borrar.id_huesped)
      toast.success(`Huésped #${borrar.id_huesped} eliminado`)
      setBorrar(null)
      cargar(buscar)
    } catch (err) {
      const info = describirError(err)
      setErrorBorrar(info.mensaje)
      if (info.tipo === "no_encontrado") cargar(buscar)
    } finally {
      setEliminando(false)
    }
  }

  // ------------------------------------------------------------ vista
  const total = lista.estado === "listo" ? lista.datos.length : null

  return (
    <StaffLayout
      titulo="Huéspedes"
      subtitulo={total === null ? "Registro de huéspedes del hotel" : `${total} huésped${total === 1 ? "" : "es"}${buscar ? " encontrados" : " registrados"}`}
      acciones={<button className="btn btn-pri" onClick={abrirCrear}>+ Nuevo huésped</button>}
    >
      <div className="tarjeta">
        <div className="barra-herramientas">
          <div className="buscador">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
            <input
              type="search"
              placeholder="Buscar por nombre, documento o correo"
              aria-label="Buscar huéspedes"
              value={buscar}
              maxLength={60}
              onChange={(e) => setBuscar(e.target.value)}
            />
          </div>
          <form onSubmit={consultarPorId} style={{ display: "flex", gap: 8 }}>
            <input
              style={{ width: 110, padding: "9px 11px", border: "1px solid #dcdcdc", borderRadius: 8, background: "#fafafa", fontSize: 14 }}
              inputMode="numeric"
              placeholder="ID"
              aria-label="Consultar huésped por id"
              value={idConsulta}
              onChange={(e) => setIdConsulta(e.target.value.replace(/\D/g, ""))}
            />
            <button className="btn btn-sec" type="submit">Consultar</button>
          </form>
        </div>

        {lista.estado === "cargando" && (
          <div className="cargando-fila" role="status"><span className="spinner" aria-hidden="true" />Cargando huéspedes...</div>
        )}

        {lista.estado === "error" && (
          <div style={{ padding: 14 }}>
            <div className="aviso aviso-error" role="alert">
              <span>{lista.error.mensaje}</span>
              <span className="acciones"><button className="btn btn-sec btn-chico" onClick={() => cargar(buscar)}>Reintentar</button></span>
            </div>
          </div>
        )}

        {lista.estado === "listo" && lista.datos.length === 0 && (
          <div className="vacio">{buscar ? `No hay huéspedes que coincidan con “${buscar}”.` : "Aún no hay huéspedes registrados."}</div>
        )}

        {lista.estado === "listo" && lista.datos.length > 0 && (
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr><th>ID</th><th>Nombre</th><th>Documento</th><th>Correo</th><th>Teléfono</th><th>Nacionalidad</th><th><span className="sr-only">Acciones</span></th></tr>
              </thead>
              <tbody>
                {lista.datos.map((h) => (
                  <tr key={h.id_huesped}>
                    <td className="num">#{h.id_huesped}</td>
                    <td style={{ fontWeight: 500 }}>{h.nombre}</td>
                    <td className="num">{h.documento}</td>
                    <td>{h.correo ?? <span style={{ color: "var(--texto-3)" }}>—</span>}</td>
                    <td className="num">{h.telefono ?? <span style={{ color: "var(--texto-3)" }}>—</span>}</td>
                    <td>{h.nacionalidad ?? <span style={{ color: "var(--texto-3)" }}>—</span>}</td>
                    <td>
                      <div className="acciones-fila">
                        <button className="btn btn-texto btn-chico" onClick={() => verDetalle(h.id_huesped)}>Ver</button>
                        <button className="btn btn-texto btn-chico" onClick={() => abrirEditar(h)}>Editar</button>
                        {esAdmin && (
                          <button className="btn btn-texto btn-chico peligro" onClick={() => { setErrorBorrar(null); setBorrar(h) }}>Eliminar</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ---------------- ventana: crear / editar ---------------- */}
      <Modal
        abierto={form.abierto}
        titulo={form.id === null ? "Nuevo huésped" : `Editar huésped #${form.id}`}
        descripcion="Los campos con * son obligatorios."
        onCerrar={cerrarForm}
        bloqueado={guardando}
        pie={
          <>
            <button type="button" className="btn btn-sec" onClick={cerrarForm} disabled={guardando}>Cancelar</button>
            <button type="submit" form="form-huesped" className="btn btn-pri" disabled={guardando}>
              {guardando ? <><span className="spinner" aria-hidden="true" />Guardando...</> : form.id === null ? "Registrar huésped" : "Guardar cambios"}
            </button>
          </>
        }
      >
        <form id="form-huesped" onSubmit={guardar} noValidate>
          <fieldset disabled={guardando} style={{ border: "none" }}>
            <div className="form-grid">
              {CAMPOS.map((c, n) => (
                <div key={c.k} className={`campo${c.ancho ? " ancho" : ""}${erroresCampo[c.k] ? " con-error" : ""}`}>
                  <label htmlFor={`h-${c.k}`}>{c.etiqueta}{c.req && <span className="req"> *</span>}</label>
                  <input
                    id={`h-${c.k}`}
                    type={c.tipo ?? "text"}
                    value={valores[c.k] ?? ""}
                    maxLength={c.max}
                    onChange={(e) => cambiar(c.k, e.target.value)}
                    aria-invalid={!!erroresCampo[c.k]}
                    aria-describedby={erroresCampo[c.k] ? `h-${c.k}-err` : undefined}
                    data-autofocus={n === 0 ? true : undefined}
                    autoComplete="off"
                  />
                  {erroresCampo[c.k]
                    ? <div id={`h-${c.k}-err`} className="msg-error">{/^[a-záéíóúñ]/.test(erroresCampo[c.k]) ? `${c.etiqueta} ${erroresCampo[c.k]}` : erroresCampo[c.k]}</div>
                    : c.ayuda && <div className="ayuda">{c.ayuda}</div>}
                </div>
              ))}
            </div>
          </fieldset>
          {errorForm && (Object.keys(erroresCampo).length === 0 || errorForm.tipo !== "conflicto") && (
            <div className={`aviso ${errorForm.tipo === "red" ? "aviso-alerta" : "aviso-error"}`} role="alert" style={{ marginTop: 16 }}>
              {errorForm.mensaje}{errorForm.tipo === "red" && " Sus datos siguen en el formulario."}
            </div>
          )}
        </form>
      </Modal>

      {/* ---------------- ventana: detalle / consulta por id ---------------- */}
      <Modal
        abierto={detalle.abierto}
        titulo="Ficha del huésped"
        tamano="sm"
        onCerrar={() => setDetalle({ abierto: false, carga: null })}
        pie={
          detalle.carga?.estado === "listo" ? (
            <>
              <button className="btn btn-sec" onClick={() => setDetalle({ abierto: false, carga: null })}>Cerrar</button>
              <button className="btn btn-pri" onClick={() => {
                const h = detalle.carga?.estado === "listo" ? detalle.carga.datos : null
                setDetalle({ abierto: false, carga: null })
                if (h) abrirEditar(h)
              }}>Editar</button>
            </>
          ) : <button className="btn btn-sec" onClick={() => setDetalle({ abierto: false, carga: null })}>Cerrar</button>
        }
      >
        {detalle.carga?.estado === "cargando" && (
          <div className="cargando-fila" role="status"><span className="spinner" aria-hidden="true" />Consultando...</div>
        )}
        {detalle.carga?.estado === "error" && (
          <div className="aviso aviso-error" role="alert">{detalle.carga.error.mensaje}</div>
        )}
        {detalle.carga?.estado === "listo" && (
          <>
            <div className="aviso aviso-ok" style={{ marginBottom: 14 }}>ID confirmado: #{detalle.carga.datos.id_huesped}</div>
            <dl className="detalle">
              <dt>Nombre</dt><dd>{detalle.carga.datos.nombre}</dd>
              <dt>Documento</dt><dd>{detalle.carga.datos.documento}</dd>
              <dt>Nacionalidad</dt><dd>{detalle.carga.datos.nacionalidad ?? "—"}</dd>
              <dt>Teléfono</dt><dd>{detalle.carga.datos.telefono ?? "—"}</dd>
              <dt>Correo</dt><dd>{detalle.carga.datos.correo ?? "—"}</dd>
            </dl>
          </>
        )}
      </Modal>

      {/* ---------------- ventana: confirmar eliminación ---------------- */}
      <ConfirmDialog
        abierto={borrar !== null}
        titulo="Eliminar huésped"
        mensaje={borrar && <>¿Eliminar a <b>{borrar.nombre}</b> (#{borrar.id_huesped})? Esta acción no se puede deshacer. No se permite si tiene reservas activas.</>}
        textoConfirmar="Eliminar"
        textoProcesando="Eliminando..."
        peligro
        procesando={eliminando}
        error={errorBorrar}
        onConfirmar={confirmarBorrado}
        onCancelar={() => { if (!eliminando) setBorrar(null) }}
      />
    </StaffLayout>
  )
}
