import { Link } from "react-router-dom"
import StaffLayout from "../components/StaffLayout"
import { useCarga } from "../hooks/useCarga"
import { resumenPanel } from "../services/gestion"
import { cop, ESTADO_CHIP, ESTADO_TEXTO, fecha } from "../services/formato"
import { leerSesion } from "../services/sesion"

/* Dashboard general del personal (semana 15): indicadores reales de GET /api/panel/resumen y accesos. */

const icono = (d: string) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d={d} /></svg>
)

export default function Panel() {
  const sesion = leerSesion()
  const [carga, cargar] = useCarga(resumenPanel, [])

  const accesos = [
    { a: "/panel/nueva-reserva", t: "Nueva reserva", s: "Consultar disponibilidad y reservar", d: "M12 5v14M5 12h14" },
    { a: "/panel/huespedes", t: "Huéspedes", s: "Registrar, editar y consultar", d: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" },
    { a: "/panel/reservas", t: "Reservas", s: "Listar, filtrar y cancelar", d: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" },
    ...(sesion?.role === "admin" ? [{ a: "/panel/admin", t: "Administración", s: "Usuarios, tarifas y reporte PDF", d: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 12h3M18 12h3M12 3v3M12 18v3" }] : []),
  ]

  return (
    <StaffLayout
      titulo="Dashboard general"
      subtitulo={carga.fase === "ok" ? `Estado del hotel al ${fecha(carga.datos.fecha)}` : "Estado del hotel"}
      acciones={<button className="btn btn-sec" onClick={cargar} disabled={carga.fase === "curso"}>{carga.fase === "curso" ? "Actualizando..." : "Actualizar"}</button>}
    >
      {carga.fase === "error" && (
        <div className="aviso aviso-error" role="alert" style={{ marginBottom: 20 }}>
          <span>No se pudieron cargar los indicadores. {carga.error.mensaje}</span>
          <span className="acciones"><button className="btn btn-sec btn-chico" onClick={cargar}>Reintentar</button></span>
        </div>
      )}

      {/* Indicadores: mientras carga o si falla no se muestran números viejos */}
      <div className="kpis">
        {[
          { etq: "Ocupación hoy", valor: carga.fase === "ok" ? `${carga.datos.ocupacion_pct}%` : "—",
            nota: carga.fase === "ok" ? `${carga.datos.ocupadas_hoy} de ${carga.datos.habitaciones} habitaciones` : "", barra: carga.fase === "ok" ? carga.datos.ocupacion_pct : null },
          { etq: "Reservas activas", valor: carga.fase === "ok" ? carga.datos.reservas_activas : "—", nota: "Confirmadas y en curso" },
          { etq: "Llegadas hoy", valor: carga.fase === "ok" ? carga.datos.llegadas_hoy : "—", nota: "Check-in previstos" },
          { etq: "Ventas del mes", valor: carga.fase === "ok" ? cop(carga.datos.ventas_mes) : "—", nota: carga.fase === "ok" ? `${carga.datos.reservas_mes} reservas (sin canceladas)` : "" },
          { etq: "Huéspedes registrados", valor: carga.fase === "ok" ? carga.datos.huespedes : "—", nota: "En la base del hotel" },
        ].map((k) => (
          <div key={k.etq} className="tarjeta kpi" aria-busy={carga.fase === "curso"}>
            <div className="etq">{k.etq}</div>
            <div className="valor">{k.valor}</div>
            <div className="nota">{k.nota || " "}</div>
            {"barra" in k && k.barra !== null && k.barra !== undefined && <div className="barra"><span style={{ width: `${Math.min(100, k.barra)}%` }} /></div>}
          </div>
        ))}
      </div>

      <div className="accesos">
        {accesos.map((x) => (
          <Link key={x.a} to={x.a} className="tarjeta acceso">
            <span className="ico">{icono(x.d)}</span>
            <span><b>{x.t}</b><small>{x.s}</small></span>
          </Link>
        ))}
      </div>

      <section className="tarjeta">
        <div className="seccion-titulo">
          <h2>Próximas llegadas (14 días)</h2>
          <Link to="/panel/reservas" className="btn btn-texto btn-chico">Ver todas</Link>
        </div>
        {carga.fase === "curso" && <div className="cargando-fila" role="status"><span className="spinner" aria-hidden="true" />Cargando...</div>}
        {carga.fase === "ok" && carga.datos.proximas_llegadas.length === 0 && <div className="vacio">No hay llegadas en los próximos 14 días.</div>}
        {carga.fase === "ok" && carga.datos.proximas_llegadas.length > 0 && (
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead><tr><th>Reserva</th><th>Huésped</th><th>Habitación</th><th>Entrada</th><th>Noches</th><th>Total</th><th>Estado</th></tr></thead>
              <tbody>
                {carga.datos.proximas_llegadas.map((r) => (
                  <tr key={r.id_reserva}>
                    <td className="num">#{r.id_reserva}</td>
                    <td style={{ fontWeight: 500 }}>{r.huesped}</td>
                    <td>{r.habitacion} · {r.tipo}</td>
                    <td>{fecha(r.fecha_entrada)}</td>
                    <td className="num">{r.noches}</td>
                    <td className="num">{cop(r.total)}</td>
                    <td><span className={`chip ${ESTADO_CHIP[r.estado]}`}>{ESTADO_TEXTO[r.estado]}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </StaffLayout>
  )
}
