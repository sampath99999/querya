import type { AskEvent, Health, RunDetail, RunSummary, SchemaResponse } from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal })
  if (!res.ok) throw new ApiError(res.status, await errorText(res))
  return (await res.json()) as T
}

async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg: string }) => d.msg).join('; ')
  } catch {
    /* fall through */
  }
  return `${res.status} ${res.statusText}`
}

export const api = {
  health: (signal?: AbortSignal) => getJson<Health>('/health', signal),
  schema: (signal?: AbortSignal) => getJson<SchemaResponse>('/schema', signal),
  runs: (limit = 50, signal?: AbortSignal) =>
    getJson<{ items: RunSummary[]; total: number }>(`/runs?limit=${limit}`, signal),
  run: (id: string, signal?: AbortSignal) => getJson<RunDetail>(`/runs/${encodeURIComponent(id)}`, signal),
}

// POST + SSE, so EventSource cannot be used; parse the stream by hand.
export async function streamAsk(
  question: string,
  onEvent: (event: AskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ question }),
    signal,
  })
  if (!res.ok || !res.body) throw new ApiError(res.status, await errorText(res))

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const parsed = parseBlock(block)
      if (parsed) onEvent(parsed)
    }
  }
  const tail = parseBlock(buffer)
  if (tail) onEvent(tail)
}

function parseBlock(block: string): AskEvent | null {
  let event = ''
  const data: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(':')) continue
    const idx = line.indexOf(':')
    const field = idx === -1 ? line : line.slice(0, idx)
    const value = idx === -1 ? '' : line.slice(idx + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  if (!event || data.length === 0) return null
  return { event, data: JSON.parse(data.join('\n')) } as AskEvent
}
