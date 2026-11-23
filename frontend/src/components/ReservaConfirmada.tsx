import Modal from "./Modal"
import logo from "../assets/image.ico"
import type { Reserva } from "../services/corte"
import { cop, fecha } from "../services/formato"

/*
 * Ventana que se abre SOLO cuando el backend confirmó la reserva (201): muestra el código real que
 * devolvió POST /api/reservas, nunca un dato supuesto por la pantalla.
 */
export default function ReservaConfirmada({ reserva, onCerrar, onVerMisReservas }: {
  reserva: Reserva | null
  onCerrar: () => void
  onVerMisReservas: () => void
}) {
  const r = reserva
  const nombre = r ? r.huesped.nombre.split(" ")[0] : ""
  return (
    <Modal
      abierto={r !== null}
      titulo="Reserva confirmada"
      onCerrar={onCerrar}
      tamano="md"
      pie={
        <>
          <button type="button" className="btn btn-sec" onClick={onCerrar}>Cerrar</button>
          <button type="button" className="btn btn-pri" onClick={onVerMisReservas} data-autofocus>Ver mis reservas</button>
        </>
      }
    >
      {r && (
        <div className="confirmacion">
          <div className="confirmacion-franja" />
          <div className="confirmacion-cabecera">
            <img src={logo} alt="Marea Dorada Resort" />
            <h3>Gracias {nombre}, su reserva está confirmada</h3>
            <p className="confirmacion-codigo">Código de la reserva: <b>#{r.id_reserva}</b></p>
          </div>

          <div className="confirmacion-bloque">
            <p className="confirmacion-hotel">MAREA DORADA RESORT &amp; SPA</p>
            <dl className="detalle">
              <dt>Huésped</dt><dd>{r.huesped.nombre}</dd>
              <dt>Habitación</dt><dd>{r.habitacion.numero} · {r.habitacion.tipo}</dd>
              <dt>Llegada</dt><dd>{fecha(r.fecha_entrada)}</dd>
              <dt>Salida</dt><dd>{fecha(r.fecha_salida)}</dd>
              <dt>Noches</dt><dd>{r.noches}</dd>
              <dt>Huéspedes</dt><dd>{r.numero_personas}</dd>
              <dt>Tarifa</dt><dd>{cop(r.tarifa_noche)} por noche</dd>
              <dt>Total</dt><dd className="confirmacion-total">{cop(r.total)} COP</dd>
              <dt>Estado</dt><dd><span className="chip chip-verde">Confirmada</span></dd>
            </dl>
          </div>

          <p className="confirmacion-nota">
            Puede consultar esta reserva en cualquier momento en <b>Mis reservas</b>.
          </p>
        </div>
      )}
    </Modal>
  )
}
