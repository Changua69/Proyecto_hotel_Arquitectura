import { useEffect, useState } from "react"
import type { CSSProperties } from "react"
import { useNavigate } from "react-router-dom"
import API from "../services/api"
import logo from "../assets/image.ico"

function Dashboard() {
  const [user, setUser] = useState<any>(null)
  const [rooms, setRooms] = useState<any[]>([])
  const navigate = useNavigate()

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
        <div style={searchGrid}>
          <div>
            <label style={searchLabel}>Check-in</label>
            <input type="date" style={searchInput} />
          </div>
          <div>
            <label style={searchLabel}>Check-out</label>
            <input type="date" style={searchInput} />
          </div>
          <div>
            <label style={searchLabel}>Huéspedes</label>
            <select style={searchInput}>
              <option>1 Huésped</option>
              <option>2 Huéspedes</option>
              <option>3 Huéspedes</option>
              <option>4+ Huéspedes</option>
            </select>
          </div>
          <div>
            <label style={searchLabel}>Tipo de Habitación</label>
            <select style={searchInput}>
              <option>Todas</option>
              <option>Estándar</option>
              <option>Suite</option>
              <option>Familiar</option>
            </select>
          </div>
          <button style={searchBtn}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            Buscar
          </button>
        </div>
      </div>

      {/* HABITACIONES */}
      <div style={container}>
        <h2 style={{ fontSize: "18px", fontWeight: 500, margin: "0 0 1.5rem", color: "#111" }}>
          Habitaciones Disponibles
        </h2>
        <div style={roomGrid}>
          {Array.isArray(rooms) && rooms.map((room) => (
            <div key={room.number} style={roomCard} onClick={() => navigate(`/rooms/${room.number}`)}>
              <div style={imgWrapper}>
                <img
                  src={room.images?.[0] || room.image || "https://via.placeholder.com/400x200"}
                  style={roomImg}
                  alt={room.type}
                />
                <span style={badge}>{room.status || "Disponible"}</span>
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
                  ${room.price?.toLocaleString("es-CO")} COP{" "}
                  <span style={{ fontSize: "12px", fontWeight: 400, color: "#888" }}>/noche</span>
                </p>
                <button
                  style={reserveBtn}
                  onClick={e => { e.stopPropagation(); navigate(`/rooms/${room.number}`) }}
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