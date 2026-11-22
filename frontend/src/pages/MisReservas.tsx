import { useEffect, useState } from "react"
import type { CSSProperties, FormEvent } from "react"
import toast from "react-hot-toast"
import { useNavigate } from "react-router-dom"
import logo from "../assets/image.ico"
import { useCarga } from "../hooks/useCarga"
import { describirError } from "../services/api"
import { listarReservas } from "../services/gestion"
import type { ReservaFila } from "../services/gestion"
import { completarMiFicha, miCuenta, miFicha } from "../services/huespedes"
import type { Huesped } from "../services/huespedes"
import { cop, ESTADO_CHIP, ESTADO_TEXTO, fecha, hoyISO } from "../services/formato"
import { cerrarSesion, leerSesion } from "../services/sesion"
import "../styles/app.css"

/*
 * Mis reservas (portal del huésped, semana 15). Solo consulta: el huésped ve las reservas que tiene.
 * Interfaz -> GET /api/huespedes/yo y GET /api/reservas -> servicios -> repositorios -> MongoDB.
 * El backend decide qué reservas son suyas (por el correo de la sesión): aunque alguien cambie la
 * pantalla, nunca recibe reservas de otro huésped.
 */

type Datos = { ficha: Huesped | null; reservas: ReservaFila[] }

async function cargarMisReservas(): Promise<Datos> {
  try {
    const ficha = await miFicha()
    return { ficha, reservas: await listarReservas({}) }
  } catch (e) {
    // 404 en /yo = la cuenta no está asociada a ningún huésped registrado (no es un fallo del sistema).
    if (describirError(e).tipo === "no_encontrado") return { ficha: null, reservas: [] }
    throw e
  }
}

export default function MisReservas() {
  const sesion = leerSesion()
  const navigate = useNavigate()
  const [carga, recargar] = useCarga(cargarMisReservas, [])

  const hoy = hoyISO()
  const activas = (r: ReservaFila) => r.estado === "CONFIRMADA" || r.estado === "EN_CURSO"
  const proximas = carga.fase === "ok" ? carga.datos.reservas.filter((r) => activas(r) && r.fecha_salida >= hoy) : []
  const historial = carga.fase === "ok" ? carga.datos.reservas.filter((r) => !proximas.includes(r)) : []

  return (
    <div style={page}>
      <nav style={navbar}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <img src={logo} style={logoImg} alt="Logo" />
          <div>
            <p style={{ margin: 0, fontSize: 14, fontWeight: 500, color: "#111" }}>Marea Dorada Resort</p>
            <p style={{ margin: 0, fontSize: 11, color: "#888" }}>Portal del Huésped</p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 13, color: "#555" }}>{sesion?.email}</span>
          <button className="btn btn-sec btn-chico" onClick={() => navigate("/dashboard")}>← Habitaciones</button>
          <button className="btn btn-sec btn-chico" onClick={() => { cerrarSesion(); navigate("/") }}>Salir</button>
        </div>
      </nav>

      <main style={{ maxWidth: 1000, margin: "0 auto", padding: "28px 20px" }}>
        <div className="panel-cabecera">
          <div>
            <h1>Mis reservas</h1>
            <p>{carga.fase === "ok" && carga.datos.ficha
              ? `${carga.datos.ficha.nombre} · Huésped #${carga.datos.ficha.id_huesped}`
              : "Consulte sus reservas en el hotel"}</p>
          </div>
          <button className="btn btn-sec" onClick={recargar} disabled={carga.fase === "curso"}>
            {carga.fase === "curso" ? "Actualizando..." : "Actualizar"}
          </button>
        </div>

        {carga.fase === "curso" && (
          <div className="tarjeta cargando-fila" role="status"><span className="spinner" aria-hidden="true" />Cargando sus reservas...</div>
        )}

        {carga.fase === "error" && (
          <div className="aviso aviso-error" role="alert">
            <span>No se pudieron cargar sus reservas. {carga.error.mensaje}</span>
            <span className="acciones"><button className="btn btn-sec btn-chico" onClick={recargar}>Reintentar</button></span>
          </div>
        )}

        {carga.fase === "ok" && !carga.datos.ficha && <CompletarDatos correo={sesion?.email ?? ""} onListo={recargar} />}

        {carga.fase === "ok" && carga.datos.ficha && carga.datos.reservas.length === 0 && (
          <div className="tarjeta vacio">Aún no tiene reservas registradas.</div>
        )}

        {carga.fase === "ok" && carga.datos.ficha && carga.datos.reservas.length > 0 && (
          <>
            <Seccion titulo="Próximas y en curso" filas={proximas} vacio="No tiene reservas próximas." />
            <Seccion titulo="Historial" filas={historial} vacio="No hay reservas anteriores ni canceladas." />
          </>
        )}
      </main>
    </div>
  )
}

/** Cuentas creadas antes de que el registro pidiera el documento: completan sus datos una sola vez. */
function CompletarDatos({ correo, onListo }: { correo: string; onListo: () => void }) {
  const [v, setV] = useState({ nombre: "", documento: "", telefono: "" })
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  // Prellena con lo que ya se escribió al registrarse: solo falta el documento.
  useEffect(() => {
    let vivo = true
    miCuenta().then((c) => {
      if (vivo) setV((x) => ({ ...x, nombre: x.nombre || c.nombre, telefono: x.telefono || (c.telefono ?? "") }))
    }).catch(() => { /* sin prellenado: el formulario sigue funcionando */ })
    return () => { vivo = false }
  }, [])

  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    if (enviando) return
    const locales: Record<string, string> = {}
    if (v.nombre.trim().length < 2) locales.nombre = "es obligatorio"
    if (!v.documento.trim()) locales.documento = "es obligatorio"
    setErrores(locales); setError(null)
    if (Object.keys(locales).length) return
    setEnviando(true)
    try {
      await completarMiFicha({ nombre: v.nombre, documento: v.documento, telefono: v.telefono || null })
      toast.success("Datos guardados")
      onListo()
    } catch (err) {
      const info = describirError(err)
      setErrores(info.campos)
      setError(info.mensaje)
    } finally {
      setEnviando(false)
    }
  }

  const campo = (k: keyof typeof v, etiqueta: string, req = false) => (
    <div className={`campo${errores[k] ? " con-error" : ""}`}>
      <label htmlFor={`f-${k}`}>{etiqueta}{req && <span className="req"> *</span>}</label>
      <input id={`f-${k}`} value={v[k]} onChange={(e) => { setV({ ...v, [k]: e.target.value }); setErrores({ ...errores, [k]: "" }) }} />
      {errores[k] && <div className="msg-error">{/^[a-záéíóúñ]/.test(errores[k]) ? `${etiqueta} ${errores[k]}` : errores[k]}</div>}
    </div>
  )

  return (
    <form className="tarjeta" style={{ padding: 20, maxWidth: 560 }} onSubmit={guardar} noValidate>
      <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Complete sus datos</h2>
      <p style={{ fontSize: 13.5, color: "var(--texto-3)", marginBottom: 16 }}>
        Su cuenta se creó antes de que el registro pidiera el documento. Complételo una sola vez: quedará
        asociado a su correo <b>{correo}</b> y aquí verá sus reservas.
      </p>
      <fieldset disabled={enviando} style={{ border: "none" }}>
        <div className="form-grid">
          <div className="ancho">{campo("nombre", "Nombre completo", true)}</div>
          {campo("documento", "Documento", true)}
          {campo("telefono", "Teléfono")}
        </div>
      </fieldset>
      {error && <div className="aviso aviso-error" role="alert">{error}</div>}
      <button className="btn btn-pri" type="submit" disabled={enviando} style={{ marginTop: 16 }}>
        {enviando ? <><span className="spinner" aria-hidden="true" />Guardando...</> : "Guardar mis datos"}
      </button>
    </form>
  )
}

function Seccion({ titulo, filas, vacio }: { titulo: string; filas: ReservaFila[]; vacio: string }) {
  return (
    <section className="tarjeta" style={{ marginBottom: 20 }}>
      <div className="seccion-titulo"><h2>{titulo}</h2><span style={{ fontSize: 13, color: "var(--texto-3)" }}>{filas.length}</span></div>
      {filas.length === 0 ? <div className="vacio" style={{ padding: 24 }}>{vacio}</div> : (
        <div className="tabla-envoltura">
          <table className="tabla">
            <thead>
              <tr><th>Reserva</th><th>Habitación</th><th>Entrada</th><th>Salida</th><th>Noches</th><th>Personas</th><th>Total</th><th>Estado</th></tr>
            </thead>
            <tbody>
              {filas.map((r) => (
                <tr key={r.id_reserva}>
                  <td className="num" style={{ fontWeight: 500 }}>#{r.id_reserva}</td>
                  <td>{r.habitacion} · {r.tipo}</td>
                  <td>{fecha(r.fecha_entrada)}</td>
                  <td>{fecha(r.fecha_salida)}</td>
                  <td className="num">{r.noches}</td>
                  <td className="num">{r.numero_personas}</td>
                  <td className="num">{cop(r.total)}</td>
                  <td><span className={`chip ${ESTADO_CHIP[r.estado]}`}>{ESTADO_TEXTO[r.estado]}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

const page: CSSProperties = { background: "#f5f5f5", minHeight: "100vh", width: "100%" }
const navbar: CSSProperties = {
  background: "white", borderBottom: "1px solid #eee", padding: "0 2rem", display: "flex",
  justifyContent: "space-between", alignItems: "center", height: 56, width: "100%", boxSizing: "border-box",
  flexWrap: "wrap", gap: 8,
}
const logoImg: CSSProperties = { width: 44, height: 44, borderRadius: 8, objectFit: "cover" }
