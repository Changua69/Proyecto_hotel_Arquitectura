import { useEffect, useRef, useState } from "react"
import type { CSSProperties } from "react"
import { useParams, useNavigate, useSearchParams } from "react-router-dom"
import ReservaConfirmada from "../components/ReservaConfirmada"
import "../styles/app.css"
import logo from "../assets/image.ico"
import toast from "react-hot-toast"
import API, { describirError } from "../services/api"
import { consultarDisponibilidad, crearReserva } from "../services/corte"
import type { Disponibilidad, Reserva } from "../services/corte"
import { miFicha } from "../services/huespedes"
import { cop, fecha, hoyISO } from "../services/formato"
import { leerSesion } from "../services/sesion"

/*
 * Semana 15: "Reservar Ahora" usa el sistema del corte (GET /api/disponibilidad y POST /api/reservas),
 * el mismo de recepción. Así la reserva queda a nombre del huésped que inició sesión, aparece en
 * "Mis reservas" y la ve el personal. La habitación concreta la asigna el backend (la libre de menor
 * número del tipo elegido).
 */
const TIPO_CORTE: Record<string, number> = { estandar: 1, "estándar": 1, familiar: 2, suite: 3 }

function RoomDetail() {
  const { number } = useParams()
  const navigate = useNavigate()
  const sesion = leerSesion()
  const [room, setRoom] = useState<any>(null)

  // Fechas y personas que vienen del buscador del portal (?entrada=&salida=&personas=)
  const [params] = useSearchParams()
  const [checkIn, setCheckIn] = useState(params.get("entrada") ?? "")
  const [checkOut, setCheckOut] = useState(params.get("salida") ?? "")
  const [personas, setPersonas] = useState(Math.max(1, Number(params.get("personas")) || 1))
  const [ventana, setVentana] = useState<Reserva | null>(null)
  const [disp, setDisp] = useState<{ fase: "nada" | "curso" | "ok" | "error"; datos?: Disponibilidad; error?: string }>({ fase: "nada" })
  const [enviando, setEnviando] = useState(false)
  const [reserva, setReserva] = useState<Reserva | null>(null)
  const turno = useRef(0)

  useEffect(() => {
    API.get("/rooms").then(res => {
      const found = res.data.find((r: any) => r.number == number)
      setRoom(found)
    }).catch(console.error)
  }, [number])

  const idTipo = room ? TIPO_CORTE[String(room.type).toLowerCase()] : undefined
  const fechasOk = !!checkIn && !!checkOut && checkOut > checkIn && checkIn >= hoyISO()

  // Tarifa y disponibilidad reales para las fechas elegidas (consulta pública, RF-02).
  useEffect(() => {
    if (!idTipo || !fechasOk) return
    const mio = ++turno.current
    const t = window.setTimeout(() => {
      setDisp({ fase: "curso" })
      consultarDisponibilidad({ id_tipo: idTipo, fecha_entrada: checkIn, fecha_salida: checkOut, personas })
        .then(d => { if (mio === turno.current) setDisp({ fase: "ok", datos: d }) })
        .catch(e => { if (mio === turno.current) setDisp({ fase: "error", error: describirError(e).mensaje }) })
    }, 250)
    return () => window.clearTimeout(t)
  }, [idTipo, checkIn, checkOut, personas, fechasOk])

  const cambiar = (f: () => void) => { f(); setReserva(null); setDisp({ fase: "nada" }) }

  const handleReserve = async () => {
    if (enviando) return
    if (!sesion) { navigate("/"); return }
    if (sesion.role !== "huesped") {
      toast("Como personal, reserve desde el panel: Nueva reserva")
      navigate("/panel/nueva-reserva")
      return
    }
    if (!checkIn || !checkOut) { toast.error("Selecciona las fechas"); return }
    if (checkOut <= checkIn) { toast.error("La salida debe ser posterior a la entrada"); return }
    if (checkIn < hoyISO()) { toast.error("La entrada no puede ser anterior a hoy"); return }
    if (!idTipo) { toast.error("Tipo de habitación desconocido"); return }

    setEnviando(true)
    try {
      let idHuesped: number
      try {
        idHuesped = (await miFicha()).id_huesped
      } catch (e) {
        if (describirError(e).tipo === "no_encontrado") {
          toast.error("Primero complete sus datos en Mis reservas")
          navigate("/mis-reservas")
          return
        }
        throw e
      }
      const r = await crearReserva({
        id_huesped: idHuesped, id_tipo: idTipo,
        fecha_entrada: checkIn, fecha_salida: checkOut, numero_personas: personas,
      })
      setReserva(r) // 201: el backend ya la guardó
      setVentana(r) // ventana de confirmación con el código real
    } catch (e) {
      toast.error(describirError(e).mensaje) // 409 sin disponibilidad, 422 capacidad, 400 fechas, red...
    } finally {
      setEnviando(false)
    }
  }

  if (!room) return <div style={{ padding: "2rem", color: "#888" }}>Cargando...</div>

  return (
    <div style={page}>

      {/* NAVBAR */}
      <nav style={navbar}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <img src={logo} style={logoImg} alt="Logo" />
          <div>
            <p style={{ margin: 0, fontSize: "14px", fontWeight: 500, color: "#111" }}>Marea Dorada Resort</p>
            <p style={{ margin: 0, fontSize: "11px", color: "#888" }}>Portal del Huésped</p>
          </div>
        </div>
        <button style={backBtn} onClick={() => navigate("/dashboard")}>← Volver</button>
      </nav>

      {/* CONTENIDO */}
      <div style={container}>
        <div style={detailCard}>

          {/* HERO */}
          <img
            src={room.images?.[0] || room.image || "https://via.placeholder.com/1200x400"}
            style={heroImg}
            alt={room.type}
          />

          <div style={contentGrid}>

            {/* COLUMNA IZQUIERDA */}
            <div>
              <div style={{ marginBottom: "1.5rem" }}>
                <span style={availBadge}>{room.status || "Disponible"}</span>
                <h1 style={{ margin: "8px 0 4px", fontSize: "22px", fontWeight: 500, color: "#111" }}>
                  {room.type} — Habitación {room.number}
                </h1>
                <p style={{ margin: 0, color: "#888", fontSize: "14px" }}>
                  Piso {room.floor || "1"} · {room.view || "Vista Ciudad"}
                </p>
              </div>

              {/* MÉTRICAS */}
              <div style={metaGrid}>
                <div style={metaItem}>
                  <p style={metaLabel}>Capacidad</p>
                  <p style={metaValue}>👥 {room.capacity} personas</p>
                </div>
                <div style={metaItem}>
                  <p style={metaLabel}>Camas</p>
                  <p style={metaValue}>🛏 {room.beds || "1 cama doble"}</p>
                </div>
                <div style={metaItem}>
                  <p style={metaLabel}>Tamaño</p>
                  <p style={metaValue}>📐 {room.size || "25 m²"}</p>
                </div>
              </div>

              {/* DESCRIPCIÓN */}
              <div style={{ marginBottom: "1.5rem" }}>
                <h3 style={sectionTitle}>Descripción</h3>
                <p style={{ color: "#555", lineHeight: "1.6", fontSize: "14px", margin: 0 }}>
                  {room.description}
                </p>
              </div>

              {/* SERVICIOS */}
              <div>
                <h3 style={sectionTitle}>Servicios incluidos</h3>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {room.services?.map((s: string, i: number) => (
                    <span key={i} style={serviceTag}>✓ {s}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* PANEL DE RESERVA */}
            <div style={bookingPanel}>
              <p style={{ margin: "0 0 2px", fontSize: "26px", fontWeight: 600, color: "#2563eb" }}>
                {disp.datos ? cop(disp.datos.tarifa_noche) : `$${room.price?.toLocaleString("es-CO")}`} COP
              </p>
              <p style={{ margin: "0 0 1.5rem", fontSize: "13px", color: "#888" }}>por noche</p>

              <div style={{ marginBottom: "1rem" }}>
                <label style={fieldLabel}>Check-in</label>
                <input
                  type="date"
                  style={fieldInput}
                  value={checkIn}
                  min={hoyISO()}
                  onChange={e => { const v = e.target.value; cambiar(() => setCheckIn(v)) }}
                />
              </div>

              <div style={{ marginBottom: "1rem" }}>
                <label style={fieldLabel}>Check-out</label>
                <input
                  type="date"
                  style={fieldInput}
                  value={checkOut}
                  min={checkIn || hoyISO()}
                  onChange={e => { const v = e.target.value; cambiar(() => setCheckOut(v)) }}
                />
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <label style={fieldLabel}>Huéspedes</label>
                <select style={fieldInput} value={personas} onChange={e => { const v = Number(e.target.value); cambiar(() => setPersonas(v)) }}>
                  {[...Array(Math.max(room.capacity || 2, personas))].map((_, i) => (
                    <option key={i} value={i + 1}>{i + 1} {i === 0 ? "Huésped" : "Huéspedes"}</option>
                  ))}
                </select>
              </div>

              {/* Disponibilidad real para las fechas elegidas */}
              {!reserva && disp.fase === "curso" && <p style={infoText}>Consultando disponibilidad...</p>}
              {!reserva && disp.fase === "error" && <p style={{ ...infoText, color: "#b91c1c" }}>{disp.error}</p>}
              {!reserva && disp.fase === "ok" && disp.datos && (disp.datos.habitaciones_disponibles.length > 0
                ? <p style={infoText}>{disp.datos.habitaciones_disponibles.length} disponible(s) · {disp.datos.noches} noche(s) · Total <b>{cop(disp.datos.tarifa_noche * disp.datos.noches)}</b></p>
                : <p style={{ ...infoText, color: "#a16207" }}>No hay habitaciones de este tipo libres en esas fechas.</p>)}

              {reserva ? (
                <div style={okBox}>
                  <p style={{ margin: "0 0 6px", fontWeight: 600 }}>Reserva #{reserva.id_reserva} confirmada</p>
                  <p style={{ margin: 0, fontSize: 13 }}>
                    Habitación {reserva.habitacion.numero} ({reserva.habitacion.tipo}) · {fecha(reserva.fecha_entrada)} → {fecha(reserva.fecha_salida)} · {cop(reserva.total)}
                  </p>
                  <button style={{ ...reserveBtn, marginTop: 12 }} onClick={() => navigate("/mis-reservas")}>Ver mis reservas</button>
                </div>
              ) : (
                <button
                  style={{ ...reserveBtn, opacity: enviando || (disp.fase === "ok" && !disp.datos?.habitaciones_disponibles.length) ? 0.6 : 1 }}
                  onClick={handleReserve}
                  disabled={enviando || (disp.fase === "ok" && !disp.datos?.habitaciones_disponibles.length)}
                >
                  {enviando ? "Enviando..." : "Reservar Ahora"}
                </button>
              )}

              <p style={{ textAlign: "center", fontSize: "12px", color: "#aaa", marginTop: "12px" }}>
                Sin cargos adicionales al reservar
              </p>
            </div>

          </div>
        </div>
      </div>
      <ReservaConfirmada
        reserva={ventana}
        onCerrar={() => setVentana(null)}
        onVerMisReservas={() => navigate("/mis-reservas")}
      />
    </div>
  )
}

/* 🔥 TODO TU DISEÑO SE MANTIENE IGUAL */
const page: CSSProperties = { background: "#f5f5f5", minHeight: "100vh", width: "100%" }
const navbar: CSSProperties = {
  background: "white", borderBottom: "1px solid #eee",
  padding: "0 2rem", display: "flex",
  justifyContent: "space-between", alignItems: "center",
  height: "56px", width: "100%", boxSizing: "border-box"
}
const backBtn: CSSProperties = {
  padding: "6px 14px", border: "1px solid #eee",
  borderRadius: "6px", background: "transparent",
  fontSize: "13px", cursor: "pointer", color: "#555"
}
const container: CSSProperties = {
  padding: "2rem", width: "100%", boxSizing: "border-box"
}
const detailCard: CSSProperties = {
  background: "white", borderRadius: "12px",
  border: "1px solid #eee", overflow: "hidden"
}
const heroImg: CSSProperties = {
  width: "100%", height: "360px", objectFit: "cover", display: "block"
}
const contentGrid: CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 340px",
  gap: "2rem", padding: "2rem"
}
const availBadge: CSSProperties = {
  background: "#dcfce7", color: "#16a34a",
  fontSize: "12px", padding: "4px 10px",
  borderRadius: "20px", fontWeight: 500
}
const metaGrid: CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
  gap: "1rem", marginBottom: "1.5rem",
  background: "#f9f9f9", borderRadius: "8px", padding: "1rem"
}
const metaItem: CSSProperties = {}
const metaLabel: CSSProperties = {
  margin: "0 0 2px", fontSize: "11px",
  color: "#aaa", textTransform: "uppercase"
}
const metaValue: CSSProperties = { margin: 0, fontSize: "13px", fontWeight: 500, color: "#333" }
const sectionTitle: CSSProperties = { margin: "0 0 8px", fontSize: "14px", fontWeight: 500, color: "#111" }
const serviceTag: CSSProperties = {
  fontSize: "12px", padding: "5px 10px",
  background: "#f0f4ff", borderRadius: "6px", color: "#2563eb"
}
const bookingPanel: CSSProperties = {
  border: "1px solid #eee", borderRadius: "12px",
  padding: "1.5rem", alignSelf: "start"
}
const fieldLabel: CSSProperties = {
  fontSize: "12px", color: "#888",
  display: "block", marginBottom: "4px"
}
const fieldInput: CSSProperties = {
  width: "100%", padding: "9px 12px",
  border: "1px solid #e0e0e0", borderRadius: "8px",
  fontSize: "13px", background: "#fafafa",
  color: "#111", boxSizing: "border-box" as const
}
const infoText: CSSProperties = { fontSize: "13px", color: "#555", margin: "0 0 12px" }
const okBox: CSSProperties = {
  background: "#ecfdf3", border: "1px solid #bbf7d0", color: "#15803d",
  borderRadius: "8px", padding: "12px 14px"
}
const reserveBtn: CSSProperties = {
  width: "100%", padding: "12px",
  background: "#111", color: "white", border: "none",
  borderRadius: "8px", fontSize: "14px",
  fontWeight: 500, cursor: "pointer"
}
const logoImg: CSSProperties = {
  width: "66px",
  height: "66px",  // 👈 quita esto si no quieres que sea circular
  objectFit: "cover",
  margin: "0 auto 1rem",
  display: "block"
}

export default RoomDetail
