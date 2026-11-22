/** $200.000 (pesos colombianos, sin decimales). */
export const cop = (n: number) => "$" + Math.round(n).toLocaleString("es-CO")

/** "2026-12-20" -> "20 dic 2026" sin problemas de zona horaria (no usa new Date("AAAA-MM-DD")). */
export function fecha(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number)
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
  return `${d} ${meses[m - 1]} ${a}`
}

/** Fecha local de hoy en AAAA-MM-DD (toISOString usaría UTC y podría dar el día siguiente). */
export function hoyISO(desplazamientoDias = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + desplazamientoDias)
  const p = (x: number) => String(x).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export const ESTADO_CHIP: Record<string, string> = {
  CONFIRMADA: "chip-azul", EN_CURSO: "chip-verde", FINALIZADA: "chip-gris", CANCELADA: "chip-rojo",
}
export const ESTADO_TEXTO: Record<string, string> = {
  CONFIRMADA: "Confirmada", EN_CURSO: "En curso", FINALIZADA: "Finalizada", CANCELADA: "Cancelada",
}
