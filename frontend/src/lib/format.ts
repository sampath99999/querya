import type { Cell } from '../types'

const compact = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })
const integer = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 })
const decimal = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const ID_COLUMN = /(^|_)(id|year)$/i

export function formatCell(value: Cell, column = ''): string {
  if (value === null) return '—'
  if (typeof value === 'number') {
    if (ID_COLUMN.test(column)) return String(value)
    return Number.isInteger(value) ? integer.format(value) : decimal.format(value)
  }
  return String(value)
}

export function formatCompact(value: number): string {
  return Math.abs(value) >= 10_000 ? compact.format(value) : decimal.format(value).replace(/\.00$/, '')
}

export function formatDuration(ms: number): string {
  if (ms < 1) return '<1 ms'
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`
}

export function formatTokens(n: number | null | undefined): string | null {
  if (!n) return null
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

export function timeAgo(iso: string): string {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

export function isNumeric(value: Cell): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}
