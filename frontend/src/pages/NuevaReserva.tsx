import { useEffect, useMemo, useRef, useState } from "react"
import type { FormEvent } from "react"
import { Link } from "react-router-dom"
import StaffLayout from "../components/StaffLayout"
import { describirError } from "../services/api"
import type { ErrorApi } from "../services/api"
import { consultarDisponibilidad, consultarReserva, crearReserva } from "../services/corte"
import type { Disponibilidad, Reserva } from "../services/corte"
import { listarHuespedes } from "../services/huespedes"
import type { Huesped } from "../services/huespedes"
import { listarTipos } from "../services/gestion"
import type { Tipo } from "../services/gestion"
import { cop, fecha, hoyISO } from "../services/formato"

/*
 * Pantalla del corte vertical (RF-02 Consultar disponibilidad + RF-04 Crear reserva).
 * Interfaz -> GET /api/disponibilidad y POST /api/reservas -> servicios -> repositorios -> MongoDB.
 *
 * Estados: inicial · en curso ("Consultando...", "Enviando...") · resultado ("Reserva #N confirmada",
 * "ID confirmado") · error. Reglas de la guía:
 * - Sin falsos éxitos: "confirmada" solo con 201 y con el id que devuelve el backend.
 * - Si se cambia un dato, se oculta la disponibilidad consultada antes (ya no corresponde).
 * - Un error oculta el resultado anterior y conserva lo escrito en el formulario.
 * - El botón se desactiva mientras se envía: no hay reservas dobles por doble clic.
 * - Contrato exacto: id_huesped, id_tipo, fecha_entrada, fecha_salida (AAAA-MM-DD), numero_personas.
 */

type Estado<T> = { fase: "inicial" } | { fase: "curso" } | { fase: "ok"; datos: T } | { fase: "error"; error: ErrorApi }

interface Datos { id_huesped: string; id_tipo: string; fecha_entrada: string; fecha_salida: string; personas: string }

const TIPOS_RESPALDO: Tipo[] = [
  { id_tipo: 1, nombre: "Estándar", capacidad_max: 2, tarifa_noche: 0 },
  { id_tipo: 2, nombre: "Familiar", capacidad_max: 4, tarifa_noche: 0 },
  { id_tipo: 3, nombre: "Suite", capacidad_max: 3, tarifa_noche: 0 },
]

const MSG_CODIGO: Record<string, string> = {
  SIN_DISPONIBILIDAD: "Ya no hay habitaciones libres de ese tipo para esas fechas. Consulte otras fechas u otro tipo.",
  CAPACIDAD_EXCEDIDA: "",
  FECHAS_INVALIDAS: "",
}

export default function NuevaReserva() {
  const [d, setD] = useState<Datos>({ id_huesped: "", id_tipo: "2", fecha_entrada: hoyISO(7), fecha_salida: hoyISO(10), personas: "2" })
  const [huespedes, setHuespedes] = useState<Huesped[] | null>(null)
  const [tipos, setTipos] = useState<Tipo[]>(TIPOS_RESPALDO)
  const [errorCatalogos, setErrorCatalogos] = useState<string | null>(null)

  const [disp, setDisp] = useState<Estado<Disponibilidad>>({ fase: "inicial" })
  const [envio, setEnvio] = useState<Estado<Reserva>>({ fase: "inicial" })
  const [claveConsultada, setClaveConsultada] = useState("")
  const enviando = useRef(false)

  // Catálogos para los selectores (si fallan, se puede escribir el id del huésped a mano).
  useEffect(() => {
    let vivo = true
    Promise.allSettled([listarHuespedes(), listarTipos()]).then(([h, t]) => {
      if (!vivo) return
      if (h.status === "fulfilled") setHuespedes(h.value)
      if (t.status === "fulfilled" && t.value.length) setTipos(t.value)
      const fallo = [h, t].find((x) => x.status === "rejected") as PromiseRejectedResult | undefined
      if (fallo) setErrorCatalogos(describirError(fallo.reason).mensaje)
    })
    return () => { vivo = false }
  }, [])

  const clave = `${d.id_tipo}|${d.fecha_entrada}|${d.fecha_salida}|${d.personas}`
  const tipoSel = tipos.find((t) => String(t.id_tipo) === d.id_tipo)

  const cambiar = (k: keyof Datos, v: string) => {
    setD((x) => ({ ...x, [k]: v }))
    // Cualquier cambio invalida lo consultado y el resultado anterior (no se muestran datos viejos).
    if (k !== "id_huesped") setDisp({ fase: "inicial" })
    setEnvio({ fase: "inicial" })
  }

  /** Validación de la pantalla (el backend vuelve a validar todo). */
  const problemas = useMemo(() => {
    const p: Partial<Record<keyof Datos, string>> = {}
    if (!d.fecha_entrada) p.fecha_entrada = "Seleccione la fecha de entrada"
    if (!d.fecha_salida) p.fecha_salida = "Seleccione la fecha de salida"
    if (d.fecha_entrada && d.fecha_salida && d.fecha_salida <= d.fecha_entrada) p.fecha_salida = "Debe ser posterior a la entrada"
    if (d.fecha_entrada && d.fecha_entrada < hoyISO()) p.fecha_entrada = "No puede ser anterior a hoy"
    const n = Number(d.personas)
    if (!Number.isInteger(n) || n < 1) p.personas = "Mínimo 1 persona"
    return p
  }, [d])

  const consultar = async (e?: FormEvent) => {
    e?.preventDefault()
    if (disp.fase === "curso" || Object.keys(problemas).some((k) => k !== "id_huesped")) return
    setDisp({ fase: "curso" })
    setEnvio({ fase: "inicial" })
    try {
      const datos = await consultarDisponibilidad({
        id_tipo: Number(d.id_tipo), fecha_entrada: d.fecha_entrada, fecha_salida: d.fecha_salida, personas: Number(d.personas),
      })
      setDisp({ fase: "ok", datos })
      setClaveConsultada(clave)
    } catch (err) {
      setDisp({ fase: "error", error: describirError(err) }) // se oculta cualquier disponibilidad anterior
    }
  }

  const idHuesped = Number(d.id_huesped)
  const puedeReservar = disp.fase === "ok" && disp.datos.habitaciones_disponibles.length > 0 &&
    claveConsultada === clave && Number.isInteger(idHuesped) && idHuesped > 0 && envio.fase !== "curso"

  const reservar = async () => {
    if (!puedeReservar || enviando.current) return
    enviando.current = true
    setEnvio({ fase: "curso" })
    try {
      const reserva = await crearReserva({
        id_huesped: idHuesped,
        id_tipo: Number(d.id_tipo),
        fecha_entrada: d.fecha_entrada, // AAAA-MM-DD, tal como lo pide el backend
        fecha_salida: d.fecha_salida,
        numero_personas: Number(d.personas),
      })
      setEnvio({ fase: "ok", datos: reserva }) // 201: el backend ya guardó y devolvió el id real
      setDisp({ fase: "inicial" })            // la disponibilidad consultada ya cambió
    } catch (err) {
      const info = describirError(err)
      setEnvio({ fase: "error", error: info })
      if (info.codigo === "SIN_DISPONIBILIDAD") setDisp({ fase: "inicial" })
    } finally {
      enviando.current = false
    }
  }

  const noches = disp.fase === "ok" ? disp.datos.noches : 0

  return (
    <StaffLayout titulo="Nueva reserva" subtitulo="RF-02 Consultar disponibilidad · RF-04 Crear reserva">
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(280px, 380px)", gap: 20, alignItems: "start" }} className="rejilla-reserva">
        {/* ---------------- formulario ---------------- */}
        <form className="tarjeta" style={{ padding: 20 }} onSubmit={consultar} noValidate>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>1. Datos de la estadía</h2>
          {errorCatalogos && <div className="aviso aviso-alerta" style={{ marginBottom: 14 }}>No se pudieron cargar las listas ({errorCatalogos}). Puede escribir el id del huésped.</div>}
          <div className="form-grid">
            <div className="campo ancho">
              <label htmlFor="r-huesped">Huésped <span className="req">*</span></label>
              {!huespedes && !errorCatalogos ? (
                <select id="r-huesped" disabled><option>Cargando huéspedes...</option></select>
              ) : huespedes ? (
                <select id="r-huesped" value={d.id_huesped} onChange={(e) => cambiar("id_huesped", e.target.value)}>
                  <option value="">Seleccione un huésped…</option>
                  {huespedes.map((h) => <option key={h.id_huesped} value={h.id_huesped}>#{h.id_huesped} · {h.nombre} · {h.documento}</option>)}
                </select>
              ) : (
                <input id="r-huesped" inputMode="numeric" placeholder="Id del huésped" value={d.id_huesped}
                  onChange={(e) => cambiar("id_huesped", e.target.value.replace(/\D/g, ""))} />
              )}
              <div className="ayuda">¿No está registrado? <Link to="/panel/huespedes">Regístrelo en Huéspedes</Link>.</div>
            </div>
            <div className="campo">
              <label htmlFor="r-tipo">Tipo de habitación <span className="req">*</span></label>
              <select id="r-tipo" value={d.id_tipo} onChange={(e) => cambiar("id_tipo", e.target.value)}>
                {tipos.map((t) => <option key={t.id_tipo} value={t.id_tipo}>{t.nombre} (hasta {t.capacidad_max})</option>)}
              </select>
            </div>
            <div className={`campo${problemas.personas ? " con-error" : ""}`}>
              <label htmlFor="r-personas">Personas <span className="req">*</span></label>
              <input id="r-personas" type="number" min={1} max={10} value={d.personas} onChange={(e) => cambiar("personas", e.target.value)} />
              {problemas.personas ? <div className="msg-error">{problemas.personas}</div>
                : tipoSel && Number(d.personas) > tipoSel.capacidad_max && <div className="ayuda" style={{ color: "var(--alerta)" }}>Supera la capacidad del tipo ({tipoSel.capacidad_max}); el backend lo rechazará.</div>}
            </div>
            <div className={`campo${problemas.fecha_entrada ? " con-error" : ""}`}>
              <label htmlFor="r-entrada">Entrada <span className="req">*</span></label>
              <input id="r-entrada" type="date" min={hoyISO()} value={d.fecha_entrada} onChange={(e) => cambiar("fecha_entrada", e.target.value)} />
              {problemas.fecha_entrada && <div className="msg-error">{problemas.fecha_entrada}</div>}
            </div>
            <div className={`campo${problemas.fecha_salida ? " con-error" : ""}`}>
              <label htmlFor="r-salida">Salida <span className="req">*</span></label>
              <input id="r-salida" type="date" min={d.fecha_entrada || hoyISO()} value={d.fecha_salida} onChange={(e) => cambiar("fecha_salida", e.target.value)} />
              {problemas.fecha_salida && <div className="msg-error">{problemas.fecha_salida}</div>}
            </div>
          </div>
          <div style={{ marginTop: 18, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button type="submit" className="btn btn-sec" disabled={disp.fase === "curso" || envio.fase === "curso" || Object.keys(problemas).length > 0}>
              {disp.fase === "curso" ? <><span className="spinner" aria-hidden="true" />Consultando...</> : "Consultar disponibilidad"}
            </button>
          </div>

          {/* ---- resultado de RF-02 ---- */}
          <div aria-live="polite">
            {disp.fase === "error" && <div className="aviso aviso-error" role="alert">{disp.error.mensaje}</div>}
            {disp.fase === "ok" && disp.datos.habitaciones_disponibles.length === 0 && (
              <div className="aviso aviso-alerta">No hay habitaciones {disp.datos.tipo} libres del {fecha(disp.datos.fecha_entrada)} al {fecha(disp.datos.fecha_salida)}. Pruebe otras fechas u otro tipo.</div>
            )}
            {disp.fase === "ok" && disp.datos.habitaciones_disponibles.length > 0 && (
              <div className="aviso aviso-ok">
                <div>
                  <b>{disp.datos.habitaciones_disponibles.length} habitación(es) {disp.datos.tipo} disponibles</b> para {disp.datos.noches} noche(s):{" "}
                  {disp.datos.habitaciones_disponibles.map((h) => h.numero).join(", ")}.
                  <div style={{ marginTop: 4 }}>Se asignará la de menor número.</div>
                </div>
              </div>
            )}
          </div>
        </form>

        {/* ---------------- resumen y confirmación ---------------- */}
        <aside className="tarjeta" style={{ padding: 20, position: "sticky", top: 20 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>2. Confirmar</h2>
          {disp.fase === "ok" && disp.datos.habitaciones_disponibles.length > 0 ? (
            <dl className="detalle" style={{ gridTemplateColumns: "110px 1fr", marginBottom: 16 }}>
              <dt>Tipo</dt><dd>{disp.datos.tipo}</dd>
              <dt>Fechas</dt><dd>{fecha(disp.datos.fecha_entrada)} → {fecha(disp.datos.fecha_salida)}</dd>
              <dt>Noches</dt><dd>{noches}</dd>
              <dt>Tarifa</dt><dd>{cop(disp.datos.tarifa_noche)} / noche</dd>
              <dt>Total estimado</dt><dd style={{ fontWeight: 600, color: "var(--acento)" }}>{cop(disp.datos.tarifa_noche * noches)}</dd>
            </dl>
          ) : envio.fase !== "ok" && (
            <p style={{ fontSize: 13.5, color: "var(--texto-3)", marginBottom: 16 }}>Consulte la disponibilidad para ver el resumen y confirmar.</p>
          )}

          {envio.fase !== "ok" && (
            <button type="button" className="btn btn-pri" style={{ width: "100%" }} onClick={reservar} disabled={!puedeReservar}>
              {envio.fase === "curso" ? <><span className="spinner" aria-hidden="true" />Enviando...</> : "Confirmar reserva"}
            </button>
          )}
          {disp.fase === "ok" && disp.datos.habitaciones_disponibles.length > 0 && !d.id_huesped && (
            <div className="ayuda" style={{ fontSize: 12, color: "var(--texto-3)", marginTop: 8 }}>Seleccione el huésped para confirmar.</div>
          )}

          <div aria-live="polite">
            {envio.fase === "error" && (
              <div className={`aviso ${envio.error.tipo === "red" ? "aviso-alerta" : "aviso-error"}`} role="alert">
                <div>
                  {MSG_CODIGO[envio.error.codigo ?? ""] || envio.error.mensaje}
                  {envio.error.tipo === "red" && (
                    <div style={{ marginTop: 6 }}>Si alcanzó a enviarse, revise <Link to="/panel/reservas">Reservas</Link> antes de intentarlo de nuevo. Sus datos siguen en el formulario.</div>
                  )}
                </div>
              </div>
            )}
            {envio.fase === "ok" && <ReservaConfirmada r={envio.datos} onOtra={() => setEnvio({ fase: "inicial" })} />}
          </div>
        </aside>
      </div>

      <ConsultaPorId />
    </StaffLayout>
  )
}

function ReservaConfirmada({ r, onOtra }: { r: Reserva; onOtra: () => void }) {
  return (
    <div className="aviso aviso-ok" style={{ display: "block" }}>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Reserva #{r.id_reserva} confirmada</div>
      <dl className="detalle" style={{ gridTemplateColumns: "100px 1fr", color: "var(--texto)" }}>
        <dt>Huésped</dt><dd>{r.huesped.nombre} (#{r.huesped.id_huesped})</dd>
        <dt>Habitación</dt><dd>{r.habitacion.numero} · {r.habitacion.tipo}</dd>
        <dt>Fechas</dt><dd>{fecha(r.fecha_entrada)} → {fecha(r.fecha_salida)} ({r.noches} noches)</dd>
        <dt>Personas</dt><dd>{r.numero_personas}</dd>
        <dt>Total</dt><dd style={{ fontWeight: 600 }}>{cop(r.total)}</dd>
        <dt>Estado</dt><dd>{r.estado}</dd>
      </dl>
      <button className="btn btn-sec btn-chico" style={{ marginTop: 12 }} onClick={onOtra}>Hacer otra reserva</button>
    </div>
  )
}

/** Consultar una reserva por id (confirmación de RF-04). Un 404 oculta lo consultado antes. */
function ConsultaPorId() {
  const [id, setId] = useState("")
  const [estado, setEstado] = useState<Estado<Reserva>>({ fase: "inicial" })

  const consultar = async (e: FormEvent) => {
    e.preventDefault()
    const n = Number(id)
    if (!Number.isInteger(n) || n <= 0 || estado.fase === "curso") return
    setEstado({ fase: "curso" })
    try {
      setEstado({ fase: "ok", datos: await consultarReserva(n) })
    } catch (err) {
      setEstado({ fase: "error", error: describirError(err) })
    }
  }

  return (
    <section className="tarjeta" style={{ padding: 20, marginTop: 20 }}>
      <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Consultar una reserva por ID</h2>
      <form onSubmit={consultar} style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <div className="campo" style={{ width: 160 }}>
          <input aria-label="Id de la reserva" inputMode="numeric" placeholder="Ej. 4" value={id}
            onChange={(e) => { setId(e.target.value.replace(/\D/g, "")); setEstado({ fase: "inicial" }) }} />
        </div>
        <button className="btn btn-sec" type="submit" disabled={!id || estado.fase === "curso"}>
          {estado.fase === "curso" ? <><span className="spinner" aria-hidden="true" />Consultando...</> : "Consultar"}
        </button>
      </form>
      <div aria-live="polite">
        {estado.fase === "error" && <div className="aviso aviso-error" role="alert">{estado.error.mensaje}</div>}
        {estado.fase === "ok" && (
          <div className="aviso aviso-info" style={{ display: "block" }}>
            <b>ID confirmado: reserva #{estado.datos.id_reserva}</b> · {estado.datos.huesped.nombre} · Habitación {estado.datos.habitacion.numero} ({estado.datos.habitacion.tipo})
            · {fecha(estado.datos.fecha_entrada)} → {fecha(estado.datos.fecha_salida)} · {cop(estado.datos.total)} · {estado.datos.estado}
          </div>
        )}
      </div>
    </section>
  )
}
