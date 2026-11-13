import { useState } from "react"
import toast from "react-hot-toast"
import type { CSSProperties } from "react"
import { useNavigate } from "react-router-dom"
import API from "../services/api"
import logo from "../assets/image.ico"

type Tab = "login" | "register"

function Login() {
  const [tab, setTab] = useState<Tab>("login")

  // LOGIN
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  // REGISTER
  const [name, setName] = useState("")
  const [regEmail, setRegEmail] = useState("")
  const [phone, setPhone] = useState("")
  const [regPassword, setRegPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")

  const navigate = useNavigate()

  // 🔹 LOGIN
  const handleLogin = async () => {
    try {
      const params = new URLSearchParams()
      params.append("username", email)
      params.append("password", password)

      const res = await API.post("/login", params, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
      })

      // 🔥 guardamos datos correctos (sin variable role inexistente)
      localStorage.setItem("user", JSON.stringify({
        email,
        role: res.data.role,
        token: res.data.access_token
      }))

      navigate("/dashboard")
    } catch (error: any) {
      const message = error.response?.data?.detail
        || (error.response ? "No fue posible iniciar sesión" : "No se pudo conectar con el servidor")
      toast.error(message)
    }
  }

  // 🔹 REGISTER
  const handleRegister = async () => {
    if (regPassword !== confirmPassword) {
      alert("Las contraseñas no coinciden")
      return
    }

    try {
      await API.post("/register", {
        name,
        email: regEmail,
        password: regPassword,
        phone
      })

      // limpiar campos
      setName("")
      setRegEmail("")
      setPhone("")
      setRegPassword("")
      setConfirmPassword("")

      toast.success("Usuario creado correctamente")

      setTab("login")
    } catch (error: any) {
      const message = error.response?.data?.detail
        || (error.response ? "No fue posible registrar el usuario" : "No se pudo conectar con el servidor")
      toast.error(message)
    }
  }

  return (
    <div style={page}>
      <div style={card}>
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <img src={logo} style={logoImg} alt="Logo" />
          <h1 style={hotelTitle}>Marea Dorada Resort</h1>
          <p style={subtitleText}>Gestión Integral de Reservas · 24 Habitaciones</p>
        </div>

        <div style={tabWrapper}>
          <button style={{ ...tabBtn, ...(tab === "login" ? tabActive : tabInactive) }} onClick={() => setTab("login")}>
            Iniciar Sesión
          </button>
          <button style={{ ...tabBtn, ...(tab === "register" ? tabActive : tabInactive) }} onClick={() => setTab("register")}>
            Registrarse
          </button>
        </div>

        {/* LOGIN */}
        {tab === "login" && (
          <div>
            <Field label="Correo Electrónico">
              <div style={inputWrapper}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#aaa" strokeWidth="2">
                  <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
                </svg>
                <input type="email" placeholder="usuario@ejemplo.com" style={inputInner}
                  value={email} onChange={e => setEmail(e.target.value)} />
              </div>
            </Field>

            <Field label="Contraseña">
              <div style={inputWrapper}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#aaa" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                <input type="password" placeholder="••••••••" style={inputInner}
                  value={password} onChange={e => setPassword(e.target.value)} />
              </div>
            </Field>

            <button style={primaryBtn} onClick={handleLogin}>Ingresar</button>
            <p style={forgotLink}>¿Olvidaste tu contraseña?</p>
          </div>
        )}

        {/* REGISTER */}
        {tab === "register" && (
          <div>
            <Field label="Nombre Completo">
              <input type="text" style={inputBlock}
                placeholder="Juan Perez"
                value={name} onChange={e => setName(e.target.value)} />
            </Field>

            <Field label="Correo Electrónico">
              <input type="email" style={inputBlock}
                placeholder="usuario@gmail.com"
                value={regEmail} onChange={e => setRegEmail(e.target.value)} />
            </Field>

            <Field label="Teléfono">
              <input type="tel" style={inputBlock}
                placeholder="3185257788"
                value={phone} onChange={e => setPhone(e.target.value)} />
            </Field>

            <Field label="Contraseña">
              <input type="password" style={inputBlock}
                placeholder="••••••••"
                value={regPassword} onChange={e => setRegPassword(e.target.value)} />
            </Field>

            <Field label="Confirmar Contraseña">
              <input type="password" style={inputBlock}
                placeholder="••••••••"
                value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} />
            </Field>

            <button style={primaryBtn} onClick={handleRegister}>
              Crear Cuenta
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "1rem" }}>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  )
}

const page: CSSProperties = {
  minHeight: "100vh", width: "100%",
  background: "#f5f5f5",
  display: "flex", alignItems: "center", justifyContent: "center",
  padding: "2rem", boxSizing: "border-box"
}
const card: CSSProperties = {
  background: "white", borderRadius: "12px",
  border: "1px solid #eee", padding: "2rem",
  width: "100%", maxWidth: "420px"
}
const hotelTitle: CSSProperties = { margin: 0, fontSize: "22px", fontWeight: 600, color: "#111" }
const subtitleText: CSSProperties = { margin: "4px 0 0", fontSize: "13px", color: "#888" }
const tabWrapper: CSSProperties = {
  display: "flex", background: "#f0f0f0",
  borderRadius: "8px", padding: "3px", marginBottom: "1.5rem"
}
const tabBtn: CSSProperties = {
  flex: 1, padding: "7px", border: "none",
  borderRadius: "6px", fontSize: "13px", cursor: "pointer"
}
const tabActive: CSSProperties = { background: "white", fontWeight: 500, color: "#111" }
const tabInactive: CSSProperties = { background: "transparent", fontWeight: 400, color: "#888" }
const labelStyle: CSSProperties = {
  fontSize: "13px", fontWeight: 500, color: "#333",
  display: "block", marginBottom: "6px"
}
const inputWrapper: CSSProperties = {
  display: "flex", alignItems: "center",
  border: "1px solid #e0e0e0", borderRadius: "8px",
  padding: "0 12px", background: "#fafafa"
}
const inputInner: CSSProperties = {
  border: "none", background: "transparent",
  padding: "10px 8px", fontSize: "14px",
  width: "100%", outline: "none", color: "#111"
}
const inputBlock: CSSProperties = {
  width: "100%", padding: "10px 12px",
  border: "1px solid #e0e0e0", borderRadius: "8px",
  background: "#fafafa", fontSize: "14px",
  color: "#111", boxSizing: "border-box" as const
}
const primaryBtn: CSSProperties = {
  width: "100%", padding: "12px",
  background: "#111", color: "white", border: "none",
  borderRadius: "8px", fontSize: "14px", fontWeight: 500,
  cursor: "pointer", marginBottom: "1rem"
}
const forgotLink: CSSProperties = {
  textAlign: "center", fontSize: "13px",
  color: "#2563eb", cursor: "pointer", margin: 0
}
const logoImg: CSSProperties = {
  width: "116px",
  height: "116px",  // 👈 quita esto si no quieres que sea circular
  objectFit: "cover",
  margin: "0 auto 1rem",
  display: "block"
}

export default Login