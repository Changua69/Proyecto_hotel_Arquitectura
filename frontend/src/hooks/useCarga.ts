import { useCallback, useEffect, useRef, useState } from "react"
import { describirError } from "../services/api"
import type { ErrorApi } from "../services/api"

export type Carga<T> = { fase: "curso" } | { fase: "ok"; datos: T } | { fase: "error"; error: ErrorApi }

/**
 * Carga datos del backend con los tres estados (en curso / resultado / error).
 * - Se vuelve a cargar cuando cambian `deps`.
 * - Si llega una respuesta vieja (otra carga empezó después), se ignora.
 * - `recargar()` muestra "en curso" de inmediato y oculta lo anterior (para botones Reintentar/Actualizar).
 */
export function useCarga<T>(fn: () => Promise<T>, deps: unknown[]): [Carga<T>, () => void] {
  const [carga, setCarga] = useState<Carga<T>>({ fase: "curso" })
  const turno = useRef(0)
  const fnRef = useRef(fn)
  useEffect(() => { fnRef.current = fn })

  const ejecutar = useCallback(() => {
    const mio = ++turno.current
    fnRef.current().then(
      (datos) => { if (mio === turno.current) setCarga({ fase: "ok", datos }) },
      (e) => { if (mio === turno.current) setCarga({ fase: "error", error: describirError(e) }) },
    )
  }, [])

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { ejecutar() }, deps)

  const recargar = useCallback(() => { setCarga({ fase: "curso" }); ejecutar() }, [ejecutar])
  return [carga, recargar]
}
