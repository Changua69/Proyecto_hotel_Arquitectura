import { useEffect, useState } from "react"
import type { FormEvent } from "react"
import toast from "react-hot-toast"
import Modal from "./Modal"
import { describirError } from "../services/api"
import { modificarReserva } from "../services/corte"
import type { ReservaFila } from "../services/gestion"
import { cop, fecha, hoyISO } from "../services/formato"

/*
 * Modificar fechas o personas de una reserva CONFIRMADA (PUT /api/reservas/{id}).
 * Lo usan recepción (Reservas) y el huésped (Mis reservas). El tipo de habitación no cambia; la tarifa
 * por noche es la acordada al reservar. El backend decide la habitación: conserva la misma si sigue
 * libre o asigna otra del mismo tipo. Si no hay ninguna, la reserva queda como estaba (409).
 */
export default function ModificarReserva({ reserva, onCerrar, onListo }: {
  reserva: ReservaFila | null
  onCerrar: () => void
  onListo: () => void
}) {
  const [entrada, setEntrada] = useState("")
  const [salida, setSalida] = useState("")
  const [personas, setPersonas] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)

  // Al abrir con otra reserva, el formulario empieza con sus datos actuales.
  useEffect(() => {
    if (!reserva) return
    setEntrada(reserva.fecha_entrada)
    setSalida(reserva.fecha_salida)
    setPersonas(reserva.numero_personas)
    setError(null)
  }, [reserva])

  const noches = entrada && salida && salida > entrada
    ? Math.round((Date.parse(salida) - Date.parse(entrada)) / 86400000) : 0
  const sinCambios = !!reserva && entrada === reserva.fecha_entrada && salida === reserva.fecha_salida
    && personas === reserva.numero_personas
  const problema = !entrada || !salida ? "Elija las dos fechas."
    : salida <= entrada ? "La salida debe ser posterior a la entrada."
      : entrada < hoyISO() ? "La entrada no puede ser anterior a hoy."
        : personas < 1 ? "Mínimo 1 persona." : null

  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    if (!reserva || guardando || problema || sinCambios) return
    setGuardando(true); setError(null)
    try {
      const r = await modificarReserva(reserva.id_reserva, { fecha_entrada: entrada, fecha_salida: salida, numero_personas: personas })
      const cambio = r.habitacion.numero !== reserva.habitacion ? ` · nueva habitación ${r.habitacion.numero}` : ""
      toast.success(`Reserva #${r.id_reserva} modificada${cambio} · ${cop(r.total)}`)
      onListo()
    } catch (err) {
      setError(describirError(err).mensaje) // la reserva sigue como estaba
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Modal
      abierto={reserva !== null}
      titulo={reserva ? `Modificar reserva #${reserva.id_reserva}` : ""}
      descripcion={reserva ? `${reserva.tipo} · habitación ${reserva.habitacion} · ${fecha(reserva.fecha_entrada)} → ${fecha(reserva.fecha_salida)}` : undefined}
      onCerrar={() => { if (!guardando) onCerrar() }}
      bloqueado={guardando}
      tamano="sm"
      pie={
        <>
          <button type="button" className="btn btn-sec" onClick={onCerrar} disabled={guardando}>Cancelar</button>
          <button type="submit" form="form-modificar" className="btn btn-pri" disabled={guardando || !!problema || sinCambios}>
            {guardando ? <><span className="spinner" aria-hidden="true" />Guardando...</> : "Guardar cambios"}
          </button>
        </>
      }
    >
      {reserva && (
        <form id="form-modificar" onSubmit={guardar} noValidate>
          <fieldset disabled={guardando} style={{ border: "none" }}>
            <div className="form-grid">
              <div className="campo">
                <label htmlFor="m-entrada">Nueva entrada</label>
                <input id="m-entrada" type="date" min={hoyISO()} value={entrada} onChange={(e) => setEntrada(e.target.value)} data-autofocus />
              </div>
              <div className="campo">
                <label htmlFor="m-salida">Nueva salida</label>
                <input id="m-salida" type="date" min={entrada || hoyISO()} value={salida} onChange={(e) => setSalida(e.target.value)} />
              </div>
              <div className="campo">
                <label htmlFor="m-personas">Personas</label>
                <input id="m-personas" type="number" min={1} max={10} value={personas} onChange={(e) => setPersonas(Number(e.target.value))} />
              </div>
              <div className="campo">
                <label>Nuevo total</label>
                <div style={{ padding: "9px 0", fontWeight: 600, color: "var(--acento)" }}>
                  {noches > 0 ? `${cop(reserva.tarifa_noche * noches)} (${noches} noche${noches === 1 ? "" : "s"})` : "—"}
                </div>
              </div>
            </div>
          </fieldset>
          <p style={{ fontSize: 12.5, color: "var(--texto-3)", marginTop: 12 }}>
            Se mantiene la tarifa acordada ({cop(reserva.tarifa_noche)} por noche). Si su habitación no está libre en las
            nuevas fechas, se asigna otra del mismo tipo.
          </p>
          {problema && !sinCambios && <div className="aviso aviso-alerta">{problema}</div>}
          {error && <div className="aviso aviso-error" role="alert">{error}</div>}
        </form>
      )}
    </Modal>
  )
}
