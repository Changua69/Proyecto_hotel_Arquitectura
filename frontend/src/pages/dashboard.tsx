import { useEffect, useState } from "react"
import type { CSSProperties, FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import toast from "react-hot-toast"
import API, { describirError } from "../services/api"
import logo from "../assets/image.ico"
import { consultarDisponibilidad } from "../services/corte"
import { cop, fecha, hoyISO } from "../services/formato"

/*
 * Buscador del portal (semana 15): filtra por tipo y número de huéspedes y, si hay fechas, consulta la
 * disponibilidad REAL de cada tipo (GET /api/disponibilidad, RF-02). Las fechas elegidas pasan a la
 * pantalla de la habitación para reservar sin volver a escribirlas.
 */
const TIPOS = [
  { clave: "estandar", id: 1, nombre: "Estándar" },
  { clave: "familiar", id: 2, nombre: "Familiar" },
  { clave: "suite", id: 3, nombre: "Suite" },
]
const claveTipo = (t: string) => String(t || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")

type InfoTipo = { libres: number; tarifa: number; noches: number } | { error: string }
interface Busqueda { entrada: string; salida: string; personas: number; tipo: string }

function Dashboard() {
  const [user, setUser] = useState<any>(null)
  const [rooms, setRooms] = useState<any[]>([])
  const navigate = useNavigate()

  // Formulario del buscador y búsqueda aplicada
  const [entrada, setEntrada] = useState("")
  const [salida, setSalida] = useState("")
  const [personas, setPersonas] = useState(1)
  const [tipo, setTipo] = useState("todas")
  const [aplicada, setAplicada] = useState<Busqueda | null>(null)
  const [porTipo, setPorTipo] = useState<Record<string, InfoTipo>>({})
  const [buscando, setBuscando] = useState(false)

  const buscar = async (e?: FormEvent) => {
    e?.preventDefault()
    if (buscando) return
    if ((entrada && !salida) || (!entrada && salida)) { toast.error("Elige las dos fechas, o ninguna"); return }
    if (entrada && salida <= entrada) { toast.error("La salida debe ser posterior a la entrada"); return }
    if (entrada && entrada < hoyISO()) { toast.error("La entrada no puede ser anterior a hoy"); return }

    const b: Busqueda = { entrada, salida, personas, tipo }
    const tipos = TIPOS.filter(t => tipo === "todas" || t.clave === tipo)
    setPorTipo({})
    if (!entrada) { setAplicada(b); return }

    setBuscando(true)
    try {
      const resultados = await Promise.all(tipos.map(async t => {
        try {
          const d = await consultarDisponibilidad({ id_tipo: t.id, fecha_entrada: entrada, fecha_salida: salida, personas })
          return [t.clave, { libres: d.habitaciones_disponibles.length, tarifa: d.tarifa_noche, noches: d.noches }] as const
        } catch (err) {
          const info = describirError(err)
          if (info.tipo === "red" || info.tipo === "servidor") throw err
          return [t.clave, { error: info.mensaje }] as const // p. ej. 422: el tipo no admite tantas personas
        }
      }))
      setPorTipo(Object.fromEntries(resultados))
      setAplicada(b)
    } catch (err) {
      setAplicada(null) // sin datos viejos: si falla, no se muestra una disponibilidad anterior
      toast.error(describirError(err).mensaje)
    } finally {
      setBuscando(false)
    }
  }

  const limpiar = () => {
    setEntrada(""); setSalida(""); setPersonas(1); setTipo("todas"); setAplicada(null); setPorTipo({})
  }

  const visibles = rooms.filter((r: any) => {
    if (!aplicada) return true
    const clave = claveTipo(r.type)
    if (aplicada.tipo !== "todas" && clave !== aplicada.tipo) return false
    const info = porTipo[clave]
    if (aplicada.entrada) return !!info && !("error" in info) && info.libres > 0
    return (r.capacity || 0) >= aplicada.personas
  })

  const irAHabitacion = (numero: number) => {
    const q = aplicada?.entrada
      ? `?entrada=${aplicada.entrada}&salida=${aplicada.salida}&personas=${aplicada.personas}`
      : ""
    navigate(`/rooms/${numero}${q}`)
  }

  useEffect(() => {
    const storedUser = localStorage.getItem("user")
    if (storedUser) setUser(JSON.parse(storedUser))
  }, [])

  useEffect(() => {
    if (user?.role === "huesped") {
      API.get("/rooms").then(res => setRooms(res.data)).catch(console.error)
    }
  }, [user])

  if (!user) return <div style={{ padding: "2rem", color: "#888" }}>Cargando...</div>

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
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "13px", color: "#555", display: "flex", alignItems: "center", gap: "5px" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
            </svg>
            {user.name || user.email}
          </span>
          {user.role === "huesped" && (
            <button style={logoutBtn} onClick={() => navigate("/mis-reservas")}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
              </svg>
              Mis reservas
            </button>
          )}
          <button
            style={logoutBtn}
            onClick={() => { localStorage.removeItem("user"); navigate("/") }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            Salir
          </button>
        </div>
      </nav>

      {/* BUSCADOR */}
      <div style={searchBar}>
        <p style={{ margin: "0 0 2px", fontWeight: 500, fontSize: "15px", color: "#111" }}>
          Buscar <span style={{ color: "#2563eb" }}>Disponibilidad</span>
        </p>
        <p style={{ margin: "0 0 1rem", fontSize: "12px", color: "#888" }}>
          Encuentra la habitación perfecta para tu estancia
        </p>
        <form style={searchGrid} onSubmit={buscar}>
          <div>
            <label style={searchLabel}>Check-in</label>
            <input type="date" style={searchInput} min={hoyISO()} value={entrada} onChange={e => setEntrada(e.target.value)} />
          </div>
          <div>
            <label style={searchLabel}>Check-out</label>
            <input type="date" style={searchInput} min={entrada || hoyISO()} value={salida} onChange={e => setSalida(e.target.value)} />
          </div>
          <div>
            <label style={searchLabel}>Huéspedes</label>
            <select style={searchInput} value={personas} onChange={e => setPersonas(Number(e.target.value))}>
              <option value={1}>1 Huésped</option>
              <option value={2}>2 Huéspedes</option>
              <option value={3}>3 Huéspedes</option>
              <option value={4}>4 Huéspedes</option>
            </select>
          </div>
          <div>
            <label style={searchLabel}>Tipo de Habitación</label>
            <select style={searchInput} value={tipo} onChange={e => setTipo(e.target.value)}>
              <option value="todas">Todas</option>
              <option value="estandar">Estándar</option>
              <option value="familiar">Familiar</option>
              <option value="suite">Suite</option>
            </select>
          </div>
          <button type="submit" style={{ ...searchBtn, opacity: buscando ? 0.6 : 1 }} disabled={buscando}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            {buscando ? "Buscando..." : "Buscar"}
          </button>
        </form>

        {aplicada && (
          <div style={resumenBusqueda}>
            <span>
              {aplicada.entrada
                ? <>Del <b>{fecha(aplicada.entrada)}</b> al <b>{fecha(aplicada.salida)}</b> · {aplicada.personas} huésped(es): </>
                : <>{aplicada.personas} huésped(es){aplicada.tipo !== "todas" ? ` · ${TIPOS.find(t => t.clave === aplicada.tipo)?.nombre}` : ""} (elige fechas para ver disponibilidad)</>}
              {aplicada.entrada && TIPOS.filter(t => porTipo[t.clave]).map(t => {
                const info = porTipo[t.clave]
                return (
                  <span key={t.clave} style={{ marginRight: 12 }}>
                    {t.nombre}: {"error" in info
                      ? <span style={{ color: "#b91c1c" }}>no admite {aplicada.personas} personas</span>
                      : info.libres > 0
                        ? <span style={{ color: "#15803d" }}>{info.libres} libre(s) · {cop(info.tarifa)}/noche</span>
                        : <span style={{ color: "#a16207" }}>sin disponibilidad</span>}
                  </span>
                )
              })}
            </span>
            <button type="button" style={limpiarBtn} onClick={limpiar}>Limpiar filtros</button>
          </div>
        )}
      </div>

      {/* HABITACIONES */}
      <div style={container}>
        <h2 style={{ fontSize: "18px", fontWeight: 500, margin: "0 0 1.5rem", color: "#111" }}>
          Habitaciones Disponibles{aplicada ? ` (${visibles.length})` : ""}
        </h2>
        {aplicada && visibles.length === 0 && (
          <p style={{ color: "#888", fontSize: 14 }}>No hay habitaciones que cumplan esos filtros. Prueba otras fechas, otro tipo o menos huéspedes.</p>
        )}
        <div style={roomGrid}>
          {Array.isArray(rooms) && visibles.map((room) => (
            <div key={room.number} style={roomCard} onClick={() => irAHabitacion(room.number)}>
              <div style={imgWrapper}>
                <img
                  src={room.images?.[0] || room.image || "https://via.placeholder.com/400x200"}
                  style={roomImg}
                  alt={room.type}
                />
                <span style={badge}>
                  {(() => {
                    const info = porTipo[claveTipo(room.type)]
                    return aplicada?.entrada && info && !("error" in info) ? `${info.libres} libre(s)` : (room.status || "Disponible")
                  })()}
                </span>
              </div>
              <div style={{ padding: "1rem" }}>
                <p style={{ margin: "0", fontWeight: 500, fontSize: "15px", color: "#111" }}>{room.type}</p>
                <p style={{ margin: "0 0 10px", fontSize: "12px", color: "#888" }}>Habitación {room.number}</p>

                <p style={metaText}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
                  </svg>
                  Hasta {room.capacity} personas
                </p>
                <p style={metaText}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  {room.floor || "Piso 1"} · {room.view || "Vista Ciudad"}
                </p>

                <div style={tagsRow}>
                  {room.services?.slice(0, 4).map((s: string, i: number) => (
                    <span key={i} style={serviceTag}>{s}</span>
                  ))}
                </div>

                <p style={priceText}>
                  {(() => {
                    const info = porTipo[claveTipo(room.type)]
                    return info && !("error" in info) ? cop(info.tarifa) : `$${room.price?.toLocaleString("es-CO")}`
                  })()} COP{" "}
                  <span style={{ fontSize: "12px", fontWeight: 400, color: "#888" }}>/noche</span>
                </p>
                <button
                  style={reserveBtn}
                  onClick={e => { e.stopPropagation(); irAHabitacion(room.number) }}
                >
                  Reservar Ahora
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const page: CSSProperties = { background: "#f5f5f5", minHeight: "100vh", width: "100%" }
const navbar: CSSProperties = {
  background: "white", borderBottom: "1px solid #eee",
  padding: "0 2rem", display: "flex",
  justifyContent: "space-between", alignItems: "center",
  height: "56px", width: "100%", boxSizing: "border-box"
}
const logoutBtn: CSSProperties = {
  display: "flex", alignItems: "center", gap: "5px",
  padding: "6px 12px", border: "1px solid #eee",
  borderRadius: "6px", background: "transparent",
  fontSize: "12px", cursor: "pointer", color: "#555"
}
const searchBar: CSSProperties = {
  background: "white", borderBottom: "1px solid #eee",
  padding: "1.5rem 2rem", width: "100%", boxSizing: "border-box"
}
const searchGrid: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr 1fr 1fr auto",
  gap: "12px", alignItems: "end", width: "100%"
}
const searchLabel: CSSProperties = {
  fontSize: "12px", color: "#888",
  display: "block", marginBottom: "4px"
}
const searchInput: CSSProperties = {
  width: "100%", padding: "8px 10px",
  border: "1px solid #e0e0e0", borderRadius: "8px",
  fontSize: "13px", background: "white",
  color: "#111", boxSizing: "border-box" as const
}
const searchBtn: CSSProperties = {
  padding: "9px 20px", background: "#111",
  color: "white", border: "none", borderRadius: "8px",
  fontSize: "13px", fontWeight: 500, cursor: "pointer",
  display: "flex", alignItems: "center", gap: "6px", whiteSpace: "nowrap" as const
}
const resumenBusqueda: CSSProperties = {
  marginTop: "12px", padding: "10px 14px", background: "#f8fafc", border: "1px solid #e5e7eb",
  borderRadius: "8px", fontSize: "13px", color: "#333", display: "flex", justifyContent: "space-between",
  alignItems: "center", gap: "12px", flexWrap: "wrap"
}
const limpiarBtn: CSSProperties = {
  padding: "6px 12px", border: "1px solid #e0e0e0", borderRadius: "6px", background: "white",
  fontSize: "12px", cursor: "pointer", color: "#555"
}
const container: CSSProperties = {
  padding: "2rem", width: "100%", boxSizing: "border-box"
}
const roomGrid: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
  gap: "1.5rem", width: "100%"
}
const roomCard: CSSProperties = {
  background: "white", borderRadius: "12px",
  border: "1px solid #eee", overflow: "hidden", cursor: "pointer"
}
const imgWrapper: CSSProperties = { position: "relative", height: "180px" }
const roomImg: CSSProperties = { width: "100%", height: "100%", objectFit: "cover" }
const badge: CSSProperties = {
  position: "absolute", top: "10px", right: "10px",
  background: "#16a34a", color: "white",
  fontSize: "11px", padding: "3px 8px",
  borderRadius: "20px", fontWeight: 500
}
const metaText: CSSProperties = {
  margin: "0 0 4px", fontSize: "12px", color: "#666",
  display: "flex", alignItems: "center", gap: "5px"
}
const tagsRow: CSSProperties = {
  display: "flex", gap: "6px",
  flexWrap: "wrap", margin: "8px 0 12px"
}
const serviceTag: CSSProperties = {
  fontSize: "11px", padding: "3px 8px",
  background: "#f0f4ff", borderRadius: "20px", color: "#555"
}
const priceText: CSSProperties = {
  margin: "0 0 12px", fontSize: "18px",
  fontWeight: 500, color: "#2563eb"
}
const reserveBtn: CSSProperties = {
  width: "100%", padding: "10px",
  background: "#111", color: "white", border: "none",
  borderRadius: "8px", fontSize: "13px",
  fontWeight: 500, cursor: "pointer"
}
const logoImg: CSSProperties = {
  width: "56px",
  height: "56px",
  borderRadius: "8px",  // o "50%" si quieres circular
  objectFit: "cover"
}
export default Dashboard