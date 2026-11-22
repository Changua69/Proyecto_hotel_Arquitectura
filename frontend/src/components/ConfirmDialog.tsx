import type { ReactNode } from "react"
import Modal from "./Modal"

/*
 * Confirmación (p. ej. "¿Eliminar huésped?"). Reemplaza window.confirm/alert, que bloquean la página
 * y no se pueden diseñar. Mientras `procesando` es true, el botón dice el texto en curso y la ventana
 * no se puede cerrar: así no hay dobles clics ni cierres a mitad de la operación.
 */
interface Props {
  abierto: boolean
  titulo: string
  mensaje: ReactNode
  textoConfirmar?: string
  textoProcesando?: string
  peligro?: boolean
  procesando?: boolean
  error?: string | null
  onConfirmar: () => void
  onCancelar: () => void
}

export default function ConfirmDialog({
  abierto, titulo, mensaje, textoConfirmar = "Confirmar", textoProcesando = "Procesando...",
  peligro = false, procesando = false, error, onConfirmar, onCancelar,
}: Props) {
  return (
    <Modal
      abierto={abierto}
      titulo={titulo}
      onCerrar={onCancelar}
      tamano="sm"
      bloqueado={procesando}
      pie={
        <>
          <button type="button" className="btn btn-sec" onClick={onCancelar} disabled={procesando}>Cancelar</button>
          <button
            type="button"
            className={`btn ${peligro ? "btn-peligro" : "btn-pri"}`}
            onClick={onConfirmar}
            disabled={procesando}
            data-autofocus
          >
            {procesando ? <><span className="spinner" aria-hidden="true" />{textoProcesando}</> : textoConfirmar}
          </button>
        </>
      }
    >
      <div className="md-mensaje">{mensaje}</div>
      {error && <div className="aviso aviso-error" role="alert">{error}</div>}
    </Modal>
  )
}
