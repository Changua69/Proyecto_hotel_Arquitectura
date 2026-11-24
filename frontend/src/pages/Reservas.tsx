import { useState } from "react"
import type { FormEvent } from "react"
import { Link } from "react-router-dom"
import toast from "react-hot-toast"
import StaffLayout from "../components/StaffLayout"
import ConfirmDialog from "../components/ConfirmDialog"
import ModificarReserva from "../components/ModificarReserva"
import { describirError } from "../services/api"
import { useCarga } from "../hooks/useCarga"
import { cancelarReserva, checkIn, checkOut, listarReservas } from "../services/gestion"
import type { ReservaFila } from "../services/gestion"
import { cop, ESTADO_CHIP, ESTADO_TEXTO, fecha, hoyISO } from "../services/formato"

/* Listado de reservas con filtros y cancelación (personal). */

interface Filtros { estado: string; desde: string; hasta: string }

export default function Reservas() {
  const [filtros, setFiltros] = useState<Filtros>({ estado: "", desde: "", hasta: "" })
  const [aplicados, setAplicados] = useState<Filtros>(filtros)
  const [cancelar, setCancelar] = useState<ReservaFila | null>(null)
  const [procesando, setProcesando] = useState(false)
  const [errorCancelar, setErrorCancelar] = useState<string | null>(null)
  const [modificar, setModificar] = useState<ReservaFila | null>(null)
  // Check-in / check-out (llegada y salida del huésped)
  const [estadia, setEstadia] = useState<{ r: ReservaFila; accion: "checkin" | "checkout" } | null>(null)
  const [errorEstadia, setErrorEstadia] = useState<string | null>(null)
  const hoy = hoyISO()

  const confirmarEstadia = async () => {
    if (!estadia || procesando) return
    setProcesando(true); setErrorEstadia(null)
    try {
      if (estadia.accion === "checkin") await checkIn(estadia.r.id_reserva)
      else await checkOut(estadia.r.id_reserva)
      toast.success(`Reserva #${estadia.r.id_reserva}: ${estadia.accion === "checkin" ? "check-in registrado" : "check-out registrado"}`)
      setEstadia(null)
      recargar()
    } catch (e) {
      setErrorEstadia(describirError(e).mensaje)
    } finally {
      setProcesando(false)
    }
  }

  const [carga, recargar] = useCarga(() => listarReservas(aplicados), [aplicados])

  const aplicar = (e: FormEvent) => {
    e.preventDefault()
    if (filtros.desde && filtros.hasta && filtros.hasta < filtros.desde) {
      toast.error("La fecha 'hasta' no puede ser anterior a 'desde'.")
      return
    }
    setAplicados({ ...filtros })
  }

  const confirmar = async () => {
    if (!cancelar || procesando) return
    setProcesando(true); setErrorCancelar(null)
    try {
      await cancelarReserva(cancelar.id_reserva)
      toast.success(`Reserva #${cancelar.id_reserva} cancelada`)
      setCancelar(null)
      recargar()
    } catch (e) {
      setErrorCancelar(describirError(e).mensaje)
    } finally {
      setProcesando(false)
    }
  }

  const total = carga.fase === "ok" ? carga.datos.reduce((s, r) => s + (r.estado === "CANCELADA" ? 0 : r.total), 0) : 0

  return (
    <StaffLayout
      titulo="Reservas"
      subtitulo={carga.fase === "ok" ? `${carga.datos.length} reserva(s) · ${cop(total)} sin contar canceladas` : "Reservas del hotel"}
      acciones={<Link to="/panel/nueva-reserva" className="btn btn-pri">+ Nueva reserva</Link>}
    >
      <div className="tarjeta">
        <form className="filtros" onSubmit={aplicar}>
          <div className="campo">
            <label htmlFor="f-estado">Estado</label>
            <select id="f-estado" value={filtros.estado} onChange={(e) => setFiltros({ ...filtros, estado: e.target.value })}>
              <option value="">Todos</option>
              {Object.entries(ESTADO_TEXTO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="campo"><label htmlFor="f-desde">Entrada desde</label>
            <input id="f-desde" type="date" value={filtros.desde} onChange={(e) => setFiltros({ ...filtros, desde: e.target.value })} /></div>
          <div className="campo"><label htmlFor="f-hasta">Entrada hasta</label>
            <input id="f-hasta" type="date" value={filtros.hasta} onChange={(e) => setFiltros({ ...filtros, hasta: e.target.value })} /></div>
          <button className="btn btn-sec" type="submit" disabled={carga.fase === "curso"}>Filtrar</button>
          {(aplicados.estado || aplicados.desde || aplicados.hasta) && (
            <button type="button" className="btn btn-texto" onClick={() => { const v = { estado: "", desde: "", hasta: "" }; setFiltros(v); setAplicados(v) }}>Limpiar</button>
          )}
        </form>

        {carga.fase === "curso" && <div className="cargando-fila" role="status"><span className="spinner" aria-hidden="true" />Cargando reservas...</div>}
        {carga.fase === "error" && (
          <div style={{ padding: 14 }}>
            <div className="aviso aviso-error" role="alert"><span>{carga.error.mensaje}</span>
              <span className="acciones"><button className="btn btn-sec btn-chico" onClick={recargar}>Reintentar</button></span></div>
          </div>
        )}
        {carga.fase === "ok" && carga.datos.length === 0 && <div className="vacio">No hay reservas con esos filtros.</div>}
        {carga.fase === "ok" && carga.datos.length > 0 && (
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead><tr><th>#</th><th>Huésped</th><th>Habitación</th><th>Entrada</th><th>Salida</th><th>Pers.</th><th>Total</th><th>Estado</th><th><span className="sr-only">Acciones</span></th></tr></thead>
              <tbody>
                {carga.datos.map((r) => (
                  <tr key={r.id_reserva}>
                    <td className="num">#{r.id_reserva}</td>
                    <td style={{ fontWeight: 500 }}>{r.huesped} <span style={{ color: "var(--texto-3)", fontWeight: 400 }}>#{r.id_huesped}</span></td>
                    <td>{r.habitacion} · {r.tipo}</td>
                    <td>{fecha(r.fecha_entrada)}</td>
                    <td>{fecha(r.fecha_salida)}</td>
                    <td className="num">{r.numero_personas}</td>
                    <td className="num">{cop(r.total)}</td>
                    <td><span className={`chip ${ESTADO_CHIP[r.estado]}`}>{ESTADO_TEXTO[r.estado]}</span></td>
                    <td><div className="acciones-fila">
                      {r.estado === "CONFIRMADA" && r.fecha_entrada <= hoy && hoy < r.fecha_salida && (
                        <button className="btn btn-texto btn-chico" onClick={() => { setErrorEstadia(null); setEstadia({ r, accion: "checkin" }) }}>Check-in</button>
                      )}
                      {r.estado === "EN_CURSO" && (
                        <button className="btn btn-texto btn-chico" onClick={() => { setErrorEstadia(null); setEstadia({ r, accion: "checkout" }) }}>Check-out</button>
                      )}
                      {r.estado === "CONFIRMADA" && (
                        <button className="btn btn-texto btn-chico" onClick={() => setModificar(r)}>Modificar</button>
                      )}
                      {r.estado === "CONFIRMADA" && (
                        <button className="btn btn-texto btn-chico peligro" onClick={() => { setErrorCancelar(null); setCancelar(r) }}>Cancelar</button>
                      )}
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog
        abierto={cancelar !== null}
        titulo="Cancelar reserva"
        mensaje={cancelar && <>¿Cancelar la reserva <b>#{cancelar.id_reserva}</b> de {cancelar.huesped} (habitación {cancelar.habitacion}, {fecha(cancelar.fecha_entrada)} → {fecha(cancelar.fecha_salida)})? La habitación quedará libre para esas fechas.</>}
        textoConfirmar="Cancelar reserva"
        textoProcesando="Cancelando..."
        peligro
        procesando={procesando}
        error={errorCancelar}
        onConfirmar={confirmar}
        onCancelar={() => { if (!procesando) setCancelar(null) }}
      />
      <ModificarReserva reserva={modificar} onCerrar={() => setModificar(null)} onListo={() => { setModificar(null); recargar() }} />

      <ConfirmDialog
        abierto={estadia !== null}
        titulo={estadia?.accion === "checkin" ? "Registrar llegada (check-in)" : "Registrar salida (check-out)"}
        mensaje={estadia && (estadia.accion === "checkin"
          ? <>¿Registrar la llegada de <b>{estadia.r.huesped}</b> a la habitación <b>{estadia.r.habitacion}</b> (reserva #{estadia.r.id_reserva})? La reserva pasa a <b>En curso</b>.</>
          : <>¿Registrar la salida de <b>{estadia.r.huesped}</b> de la habitación <b>{estadia.r.habitacion}</b> (reserva #{estadia.r.id_reserva})? La reserva pasa a <b>Finalizada</b>{estadia.r.fecha_salida > hoy ? " y las noches que no usó quedan libres" : ""}.</>)}
        textoConfirmar={estadia?.accion === "checkin" ? "Registrar check-in" : "Registrar check-out"}
        textoProcesando="Guardando..."
        procesando={procesando && estadia !== null}
        error={errorEstadia}
        onConfirmar={confirmarEstadia}
        onCancelar={() => { if (!procesando) setEstadia(null) }}
      />
    </StaffLayout>
  )
}
