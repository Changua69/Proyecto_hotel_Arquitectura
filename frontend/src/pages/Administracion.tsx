import { useState } from "react"
import type { FormEvent } from "react"
import toast from "react-hot-toast"
import StaffLayout from "../components/StaffLayout"
import Modal from "../components/Modal"
import ConfirmDialog from "../components/ConfirmDialog"
import { describirError } from "../services/api"
import type { ErrorApi } from "../services/api"
import { useCarga } from "../hooks/useCarga"
import type { Carga } from "../hooks/useCarga"
import {
  actualizarTipo, cambiarRol, crearUsuario, descargarReportePdf, eliminarUsuario, listarTipos, listarUsuarios, reporteVentas,
} from "../services/gestion"
import type { Reporte, Tipo, Usuario } from "../services/gestion"
import { cop, ESTADO_TEXTO, fecha, hoyISO } from "../services/formato"
import { leerSesion, NOMBRE_ROL } from "../services/sesion"
import type { Rol } from "../services/sesion"

/* Módulo de Administración (solo admin): usuarios y roles, tarifas, y reporte de ventas en PDF. */

type Pestana = "reporte" | "usuarios" | "tarifas"

export default function Administracion() {
  const [pestana, setPestana] = useState<Pestana>("reporte")
  const tabs: [Pestana, string][] = [["reporte", "Reporte de ventas"], ["usuarios", "Usuarios y roles"], ["tarifas", "Tarifas y capacidad"]]
  return (
    <StaffLayout titulo="Administración" subtitulo="Solo para el rol administrador">
      <div className="pestanas" role="tablist">
        {tabs.map(([k, t]) => (
          <button key={k} role="tab" className="pestana" aria-selected={pestana === k} onClick={() => setPestana(k)}>{t}</button>
        ))}
      </div>
      {pestana === "reporte" && <ReporteVentas />}
      {pestana === "usuarios" && <Usuarios />}
      {pestana === "tarifas" && <Tarifas />}
    </StaffLayout>
  )
}

// ======================================================================= reporte de ventas
function primerDiaMes() { return hoyISO().slice(0, 8) + "01" }
function ultimoDiaMes() {
  const [a, m] = hoyISO().split("-").map(Number)
  const d = new Date(a, m, 0).getDate()
  return `${a}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`
}

function ReporteVentas() {
  const [desde, setDesde] = useState(primerDiaMes())
  const [hasta, setHasta] = useState(ultimoDiaMes())
  const [vista, setVista] = useState<Carga<Reporte> | null>(null)
  const [descargando, setDescargando] = useState(false)
  const [errorPdf, setErrorPdf] = useState<ErrorApi | null>(null)
  const invalido = !desde || !hasta || hasta < desde

  const ver = async (e?: FormEvent) => {
    e?.preventDefault()
    if (invalido) return
    setVista({ fase: "curso" }); setErrorPdf(null)
    try { setVista({ fase: "ok", datos: await reporteVentas(desde, hasta) }) } catch (err) { setVista({ fase: "error", error: describirError(err) }) }
  }

  const descargar = async () => {
    if (invalido || descargando) return
    setDescargando(true); setErrorPdf(null)
    try {
      const nombre = await descargarReportePdf(desde, hasta)
      toast.success(`Descargado: ${nombre}`)
    } catch (err) {
      // Con responseType "blob" el error del backend llega como Blob: se lee para mostrar el mensaje real.
      let info = describirError(err)
      const datos = (err as { response?: { data?: unknown } }).response?.data
      if (datos instanceof Blob) {
        try { const j = JSON.parse(await datos.text()); info = { ...info, mensaje: j.detail || info.mensaje, codigo: j.codigo ?? info.codigo } } catch { /* sin JSON */ }
      }
      setErrorPdf(info)
    } finally {
      setDescargando(false)
    }
  }

  return (
    <div className="tarjeta">
      <form className="filtros" onSubmit={ver}>
        <div className="campo"><label htmlFor="rv-desde">Entrada desde</label>
          <input id="rv-desde" type="date" value={desde} onChange={(e) => { setDesde(e.target.value); setVista(null) }} /></div>
        <div className={`campo${hasta && desde && hasta < desde ? " con-error" : ""}`}><label htmlFor="rv-hasta">Entrada hasta</label>
          <input id="rv-hasta" type="date" value={hasta} min={desde} onChange={(e) => { setHasta(e.target.value); setVista(null) }} /></div>
        <button className="btn btn-sec" type="submit" disabled={invalido || vista?.fase === "curso"}>
          {vista?.fase === "curso" ? <><span className="spinner" aria-hidden="true" />Calculando...</> : "Ver resumen"}
        </button>
        <button className="btn btn-pri" type="button" onClick={descargar} disabled={invalido || descargando}>
          {descargando ? <><span className="spinner" aria-hidden="true" />Generando PDF...</> : "Descargar PDF"}
        </button>
      </form>
      <div style={{ padding: 16 }} aria-live="polite">
        {invalido && <div className="aviso aviso-alerta">La fecha final no puede ser anterior a la inicial.</div>}
        {errorPdf && <div className="aviso aviso-error" role="alert">No se pudo generar el PDF. {errorPdf.mensaje}</div>}
        {!vista && !errorPdf && !invalido && <p style={{ fontSize: 13.5, color: "var(--texto-3)" }}>Ventas = reservas no canceladas cuya fecha de entrada está en el rango. Vea el resumen o descargue el PDF.</p>}
        {vista?.fase === "error" && <div className="aviso aviso-error" role="alert">{vista.error.mensaje}</div>}
        {vista?.fase === "ok" && (
          <>
            <div className="kpis" style={{ marginBottom: 14 }}>
              {[["Ingresos", cop(vista.datos.total)], ["Reservas", vista.datos.reservas_vendidas], ["Noches", vista.datos.noches], ["Canceladas (no suman)", vista.datos.canceladas]].map(([e, v]) => (
                <div key={String(e)} className="tarjeta kpi"><div className="etq">{e}</div><div className="valor" style={{ fontSize: 22 }}>{v}</div></div>
              ))}
            </div>
            {vista.datos.por_tipo.length === 0 ? <div className="vacio">No hay ventas entre el {fecha(vista.datos.desde)} y el {fecha(vista.datos.hasta)}.</div> : (
              <div className="tabla-envoltura">
                <table className="tabla">
                  <thead><tr><th>Tipo</th><th>Reservas</th><th>Noches</th><th>Ingresos</th></tr></thead>
                  <tbody>
                    {vista.datos.por_tipo.map((l) => (
                      <tr key={l.grupo}><td style={{ fontWeight: 500 }}>{l.grupo}</td><td className="num">{l.reservas}</td><td className="num">{l.noches}</td><td className="num">{cop(l.total)}</td></tr>
                    ))}
                  </tbody>
                </table>
                <p style={{ fontSize: 12.5, color: "var(--texto-3)", marginTop: 10 }}>
                  Por estado: {vista.datos.por_estado.map((l) => `${ESTADO_TEXTO[l.grupo] ?? l.grupo} ${l.reservas}`).join(" · ")}
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ======================================================================= usuarios
const ROLES: Rol[] = ["admin", "recepcionista", "huesped"]
const NUEVO = { email: "", nombre: "", rol: "recepcionista" as Rol, clave: "" }

function Usuarios() {
  const yo = leerSesion()?.email
  const [carga, cargar] = useCarga(listarUsuarios, [])
  const [abierto, setAbierto] = useState(false)
  const [v, setV] = useState(NUEVO)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [errorForm, setErrorForm] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [cambiando, setCambiando] = useState<string | null>(null)
  const [borrar, setBorrar] = useState<Usuario | null>(null)
  const [borrando, setBorrando] = useState(false)
  const [errorBorrar, setErrorBorrar] = useState<string | null>(null)


  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    if (guardando) return
    setGuardando(true); setErrores({}); setErrorForm(null)
    try {
      const u = await crearUsuario(v)
      toast.success(`Cuenta ${u.email} creada (${NOMBRE_ROL[u.rol]})`)
      setAbierto(false); setV(NUEVO); cargar()
    } catch (err) {
      const info = describirError(err)
      setErrores(info.campos); setErrorForm(info.mensaje)
    } finally { setGuardando(false) }
  }

  const rol = async (u: Usuario, nuevo: string) => {
    if (nuevo === u.rol || cambiando) return
    setCambiando(u.email)
    try {
      await cambiarRol(u.email, nuevo)
      toast.success(`${u.email} ahora es ${NOMBRE_ROL[nuevo as Rol]}`)
      cargar()
    } catch (err) {
      toast.error(describirError(err).mensaje) // la tabla conserva el rol real (no cambia en pantalla)
    } finally { setCambiando(null) }
  }

  const confirmarBorrado = async () => {
    if (!borrar || borrando) return
    setBorrando(true); setErrorBorrar(null)
    try {
      await eliminarUsuario(borrar.email)
      toast.success(`Cuenta ${borrar.email} eliminada`)
      setBorrar(null); cargar()
    } catch (err) { setErrorBorrar(describirError(err).mensaje) } finally { setBorrando(false) }
  }

  const campo = (k: keyof typeof NUEVO, etiqueta: string, tipo = "text", ayuda?: string) => (
    <div className={`campo${errores[k] ? " con-error" : ""}`}>
      <label htmlFor={`u-${k}`}>{etiqueta} <span className="req">*</span></label>
      <input id={`u-${k}`} type={tipo} value={v[k]} autoComplete={tipo === "password" ? "new-password" : "off"}
        data-autofocus={k === "email" ? true : undefined}
        onChange={(e) => { setV({ ...v, [k]: e.target.value }); setErrores({ ...errores, [k]: "" }) }} />
      {errores[k] ? <div className="msg-error">{etiqueta} {errores[k]}</div> : ayuda && <div className="ayuda">{ayuda}</div>}
    </div>
  )

  return (
    <div className="tarjeta">
      <div className="seccion-titulo">
        <h2>Cuentas de acceso</h2>
        <button className="btn btn-pri btn-chico" onClick={() => { setV(NUEVO); setErrores({}); setErrorForm(null); setAbierto(true) }}>+ Nueva cuenta</button>
      </div>
      {carga.fase === "curso" && <div className="cargando-fila" role="status"><span className="spinner" aria-hidden="true" />Cargando cuentas...</div>}
      {carga.fase === "error" && <div style={{ padding: 14 }}><div className="aviso aviso-error" role="alert"><span>{carga.error.mensaje}</span><span className="acciones"><button className="btn btn-sec btn-chico" onClick={cargar}>Reintentar</button></span></div></div>}
      {carga.fase === "ok" && (
        <div className="tabla-envoltura">
          <table className="tabla">
            <thead><tr><th>Correo</th><th>Nombre</th><th>Rol</th><th><span className="sr-only">Acciones</span></th></tr></thead>
            <tbody>
              {carga.datos.map((u) => (
                <tr key={u.email}>
                  <td style={{ fontWeight: 500 }}>{u.email}{u.email === yo && <span className="chip chip-gris" style={{ marginLeft: 8 }}>Usted</span>}</td>
                  <td>{u.nombre || "—"}</td>
                  <td>
                    <div className="campo" style={{ maxWidth: 170 }}>
                      <select aria-label={`Rol de ${u.email}`} value={u.rol} disabled={u.email === yo || cambiando === u.email} onChange={(e) => rol(u, e.target.value)}>
                        {ROLES.map((r) => <option key={r} value={r}>{NOMBRE_ROL[r]}</option>)}
                      </select>
                    </div>
                  </td>
                  <td><div className="acciones-fila">
                    {u.email !== yo && <button className="btn btn-texto btn-chico peligro" onClick={() => { setErrorBorrar(null); setBorrar(u) }}>Eliminar</button>}
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal abierto={abierto} titulo="Nueva cuenta" descripcion="La contraseña se guarda cifrada (bcrypt)." onCerrar={() => !guardando && setAbierto(false)} bloqueado={guardando}
        pie={<>
          <button className="btn btn-sec" type="button" onClick={() => setAbierto(false)} disabled={guardando}>Cancelar</button>
          <button className="btn btn-pri" type="submit" form="form-usuario" disabled={guardando}>{guardando ? <><span className="spinner" aria-hidden="true" />Guardando...</> : "Crear cuenta"}</button>
        </>}>
        <form id="form-usuario" onSubmit={guardar} noValidate>
          <fieldset disabled={guardando} style={{ border: "none" }}>
            <div className="form-grid">
              {campo("email", "Correo", "email")}
              {campo("nombre", "Nombre")}
              <div className={`campo${errores.rol ? " con-error" : ""}`}>
                <label htmlFor="u-rol">Rol <span className="req">*</span></label>
                <select id="u-rol" value={v.rol} onChange={(e) => setV({ ...v, rol: e.target.value as Rol })}>
                  {ROLES.map((r) => <option key={r} value={r}>{NOMBRE_ROL[r]}</option>)}
                </select>
              </div>
              {campo("clave", "Contraseña", "password", "Mínimo 8 caracteres")}
            </div>
          </fieldset>
          {errorForm && <div className="aviso aviso-error" role="alert" style={{ marginTop: 14 }}>{errorForm}</div>}
        </form>
      </Modal>

      <ConfirmDialog abierto={borrar !== null} titulo="Eliminar cuenta"
        mensaje={borrar && <>¿Eliminar la cuenta <b>{borrar.email}</b> ({NOMBRE_ROL[borrar.rol]})? Ya no podrá iniciar sesión.</>}
        textoConfirmar="Eliminar" textoProcesando="Eliminando..." peligro procesando={borrando} error={errorBorrar}
        onConfirmar={confirmarBorrado} onCancelar={() => { if (!borrando) setBorrar(null) }} />
    </div>
  )
}

// ======================================================================= tarifas
function Tarifas() {
  const [carga, cargar] = useCarga(listarTipos, [])
  const [editar, setEditar] = useState<Tipo | null>(null)
  const [cap, setCap] = useState("")
  const [tarifa, setTarifa] = useState("")
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [errorForm, setErrorForm] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)


  const abrir = (t: Tipo) => { setEditar(t); setCap(String(t.capacidad_max)); setTarifa(String(t.tarifa_noche)); setErrores({}); setErrorForm(null) }

  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    if (!editar || guardando) return
    setGuardando(true); setErrores({}); setErrorForm(null)
    try {
      const t = await actualizarTipo(editar.id_tipo, Number(cap), Number(tarifa))
      toast.success(`${t.nombre}: ${cop(t.tarifa_noche)} por noche, hasta ${t.capacidad_max} personas`)
      setEditar(null); cargar()
    } catch (err) {
      const info = describirError(err)
      setErrores(info.campos); setErrorForm(info.mensaje)
    } finally { setGuardando(false) }
  }

  return (
    <div className="tarjeta">
      <div className="seccion-titulo"><h2>Tipos de habitación</h2></div>
      {carga.fase === "curso" && <div className="cargando-fila" role="status"><span className="spinner" aria-hidden="true" />Cargando...</div>}
      {carga.fase === "error" && <div style={{ padding: 14 }}><div className="aviso aviso-error" role="alert"><span>{carga.error.mensaje}</span><span className="acciones"><button className="btn btn-sec btn-chico" onClick={cargar}>Reintentar</button></span></div></div>}
      {carga.fase === "ok" && (
        <div className="tabla-envoltura">
          <table className="tabla">
            <thead><tr><th>ID</th><th>Tipo</th><th>Capacidad</th><th>Tarifa por noche</th><th><span className="sr-only">Acciones</span></th></tr></thead>
            <tbody>
              {carga.datos.map((t) => (
                <tr key={t.id_tipo}>
                  <td className="num">{t.id_tipo}</td><td style={{ fontWeight: 500 }}>{t.nombre}</td>
                  <td className="num">{t.capacidad_max} personas</td><td className="num">{cop(t.tarifa_noche)}</td>
                  <td><div className="acciones-fila"><button className="btn btn-texto btn-chico" onClick={() => abrir(t)}>Editar</button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: 12.5, color: "var(--texto-3)", padding: "10px 16px 14px" }}>El cambio aplica a las reservas nuevas; las existentes conservan la tarifa con la que se crearon.</p>
        </div>
      )}

      <Modal abierto={editar !== null} titulo={`Editar ${editar?.nombre ?? ""}`} tamano="sm" onCerrar={() => !guardando && setEditar(null)} bloqueado={guardando}
        pie={<>
          <button className="btn btn-sec" type="button" onClick={() => setEditar(null)} disabled={guardando}>Cancelar</button>
          <button className="btn btn-pri" type="submit" form="form-tipo" disabled={guardando}>{guardando ? <><span className="spinner" aria-hidden="true" />Guardando...</> : "Guardar"}</button>
        </>}>
        <form id="form-tipo" onSubmit={guardar} noValidate>
          <fieldset disabled={guardando} style={{ border: "none" }}>
            <div className="form-grid">
              <div className={`campo${errores.capacidad_max ? " con-error" : ""}`}>
                <label htmlFor="t-cap">Capacidad máxima</label>
                <input id="t-cap" type="number" min={1} max={10} value={cap} onChange={(e) => setCap(e.target.value)} data-autofocus />
                {errores.capacidad_max && <div className="msg-error">Capacidad {errores.capacidad_max}</div>}
              </div>
              <div className={`campo${errores.tarifa_noche ? " con-error" : ""}`}>
                <label htmlFor="t-tarifa">Tarifa por noche (COP)</label>
                <input id="t-tarifa" type="number" min={1} step={1000} value={tarifa} onChange={(e) => setTarifa(e.target.value)} />
                {errores.tarifa_noche && <div className="msg-error">Tarifa {errores.tarifa_noche}</div>}
              </div>
            </div>
          </fieldset>
          {errorForm && <div className="aviso aviso-error" role="alert" style={{ marginTop: 14 }}>{errorForm}</div>}
        </form>
      </Modal>
    </div>
  )
}
