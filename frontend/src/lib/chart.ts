import type { Cell } from '../types'
import { isNumeric } from './format'

export interface ChartSpec {
  type: 'bar' | 'line'
  label: string
  series: string[]
  data: Record<string, string | number>[]
}

const TEMPORAL = /^\d{4}(-\d{2}(-\d{2})?)?$/
const MAX_POINTS = 60
const MAX_SERIES = 3

function looksTemporal(values: Cell[]): boolean {
  return values.every((v) => v !== null && TEMPORAL.test(String(v)))
}

// Picks a chart only when the result is clearly "one label column + a few numbers".
export function inferChart(columns: string[], rows: Cell[][]): ChartSpec | null {
  if (rows.length < 2 || rows.length > MAX_POINTS || columns.length < 2) return null

  const numeric = columns.map((_, i) => rows.every((r) => r[i] === null || isNumeric(r[i])))
  const labelCandidates = columns.map((_, i) => i).filter((i) => !numeric[i])
  let labelIdx: number
  if (labelCandidates.length === 1) {
    labelIdx = labelCandidates[0]
  } else if (labelCandidates.length === 0 && looksTemporal(rows.map((r) => r[0]))) {
    labelIdx = 0 // e.g. a numeric year column
  } else {
    return null
  }

  const seriesIdx = columns
    .map((_, i) => i)
    .filter((i) => i !== labelIdx && numeric[i] && !/(^|_)id$/i.test(columns[i]))
    .slice(0, MAX_SERIES)
  if (seriesIdx.length === 0) return null

  const labels = rows.map((r) => r[labelIdx])
  const label = columns[labelIdx]
  const series = seriesIdx.map((i) => columns[i])
  const data = rows.map((r) => {
    const point: Record<string, string | number> = { [label]: String(r[labelIdx] ?? '—') }
    seriesIdx.forEach((i) => {
      point[columns[i]] = (r[i] as number | null) ?? 0
    })
    return point
  })
  return { type: looksTemporal(labels) ? 'line' : 'bar', label, series, data }
}
