import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { Toaster } from "react-hot-toast"
import Login from "../pages/Login"
import Dashboard from "../pages/dashboard"
import RoomDetail from "../pages/RoomDetail"
import MisReservas from "../pages/MisReservas"
import Panel from "../pages/Panel"
import Huespedes from "../pages/Huespedes"
import NuevaReserva from "../pages/NuevaReserva"
import Reservas from "../pages/Reservas"
import Administracion from "../pages/Administracion"
import RequireRole from "../components/RequireRole"

const PERSONAL = ["recepcionista", "admin"] as const

function AppRoutes() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        containerStyle={{ zIndex: 3000 }} // los avisos quedan por encima de las ventanas emergentes
        toastOptions={{
          duration: 3500,
          style: { background: "#111", color: "#fff", borderRadius: "8px", fontSize: "14px" },
        }}
      />

      <Routes>
        <Route path="/" element={<Login />} />

        {/* Portal del huésped (semanas anteriores) */}
        <Route path="/dashboard" element={<RequireRole roles={["huesped", ...PERSONAL]}><Dashboard /></RequireRole>} />
        <Route path="/mis-reservas" element={<RequireRole roles={["huesped"]}><MisReservas /></RequireRole>} />
        <Route path="/rooms/:number" element={<RequireRole roles={["huesped", ...PERSONAL]}><RoomDetail /></RequireRole>} />

        {/* Panel del personal (semana 15) */}
        <Route path="/panel" element={<RequireRole roles={[...PERSONAL]}><Panel /></RequireRole>} />
        <Route path="/panel/nueva-reserva" element={<RequireRole roles={[...PERSONAL]}><NuevaReserva /></RequireRole>} />
        <Route path="/panel/huespedes" element={<RequireRole roles={[...PERSONAL]}><Huespedes /></RequireRole>} />
        <Route path="/panel/reservas" element={<RequireRole roles={[...PERSONAL]}><Reservas /></RequireRole>} />
        <Route path="/panel/admin" element={<RequireRole roles={["admin"]}><Administracion /></RequireRole>} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default AppRoutes
