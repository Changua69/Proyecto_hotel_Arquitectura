import { useEffect, useState } from "react"
import type { CSSProperties } from "react"
import { useParams, useNavigate } from "react-router-dom"
import logo from "../assets/image.ico"
import toast from "react-hot-toast"
import API from "../services/api"

function RoomDetail() {
  const { number } = useParams()
  const navigate = useNavigate()
  const [room, setRoom] = useState<any>(null)

  // 🔥 NUEVOS ESTADOS (NO TOCAN DISEÑO)
  const [checkIn, setCheckIn] = useState("")
  const [checkOut, setCheckOut] = useState("")

  useEffect(() => {
    API.get("/rooms").then(res => {
      const found = res.data.find((r: any) => r.number == number)
      setRoom(found)
    }).catch(console.error)
  }, [number])

  // 🔥 FUNCIÓN RESERVAR
  const handleReserve = async () => {
    const user = JSON.parse(localStorage.getItem("user") || "{}")

    if (!checkIn || !checkOut) {
      toast.error("Selecciona las fechas")
      return
    }

    if (checkOut <= checkIn) {
      toast.error("Fechas inválidas")
      return
    }

    try {
      const res = await API.post(
        "/reservations/create",
        {
          room_number: room.number,
          guest_email: user.email,
          check_in: checkIn,
          check_out: checkOut
        },
        {
          headers: {
            Authorization: `Bearer ${user.token}`
          }
        }
      )

      toast.success(res.data.message)

    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Error al reservar")
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
                ${room.price?.toLocaleString("es-CO")} COP
              </p>
              <p style={{ margin: "0 0 1.5rem", fontSize: "13px", color: "#888" }}>por noche</p>

              <div style={{ marginBottom: "1rem" }}>
                <label style={fieldLabel}>Check-in</label>
                <input
                  type="date"
                  style={fieldInput}
                  value={checkIn}
                  onChange={e => setCheckIn(e.target.value)}
                />
              </div>

              <div style={{ marginBottom: "1rem" }}>
                <label style={fieldLabel}>Check-out</label>
                <input
                  type="date"
                  style={fieldInput}
                  value={checkOut}
                  onChange={e => setCheckOut(e.target.value)}
                />
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <label style={fieldLabel}>Huéspedes</label>
                <select style={fieldInput}>
                  {[...Array(room.capacity || 2)].map((_, i) => (
                    <option key={i}>{i + 1} {i === 0 ? "Huésped" : "Huéspedes"}</option>
                  ))}
                </select>
              </div>

              <button style={reserveBtn} onClick={handleReserve}>
                Reservar Ahora
              </button>

              <p style={{ textAlign: "center", fontSize: "12px", color: "#aaa", marginTop: "12px" }}>
                Sin cargos adicionales al reservar
              </p>
            </div>

          </div>
        </div>
      </div>
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
const logoBox: CSSProperties = {
  width: "32px", height: "32px", background: "#2563eb",
  borderRadius: "6px", display: "flex",
  alignItems: "center", justifyContent: "center"
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