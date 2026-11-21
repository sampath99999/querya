import { useCallback, useRef, useState } from 'react'
import { streamAsk } from '../api'
import type { RunViewModel } from '../components/RunView'

function blankRun(question: string): RunViewModel {
  return {
    id: crypto.randomUUID(),
    question,
    status: 'running',
    answer: null,
    error: null,
    sql: null,
    columns: [],
    rows: [],
    truncated: false,
    steps: [],
    latencyMs: null,
    llmCalls: 0,
    sqlAttempts: 0,
    tokens: 0,
    model: null,
  }
}

export function useAsk(onFinished?: () => void) {
  const [turns, setTurns] = useState<RunViewModel[]>([])
  const controller = useRef<AbortController | null>(null)

  const patch = (id: string, update: (run: RunViewModel) => RunViewModel) =>
    setTurns((all) => all.map((t) => (t.id === id ? update(t) : t)))

  const ask = useCallback(
    async (question: string) => {
      controller.current?.abort()
      const abort = new AbortController()
      controller.current = abort
      const run = blankRun(question)
      let id = run.id
      setTurns((all) => [...all, run])

      try {
        await streamAsk(
          question,
          (event) => {
            switch (event.event) {
              case 'run': {
                const runId = event.data.run_id
                patch(id, (r) => ({ ...r, id: runId, model: event.data.model }))
                id = runId
                break
              }
              case 'step':
                patch(id, (r) => ({ ...r, steps: [...r.steps, event.data] }))
                break
              case 'result': {
                const res = event.data
                patch(id, (r) => ({
                  ...r,
                  status: res.status,
                  answer: res.answer,
                  error: res.error,
                  sql: res.sql,
                  columns: res.columns,
                  rows: res.rows,
                  truncated: res.truncated,
                  latencyMs: res.latency_ms,
                  llmCalls: res.llm_calls,
                  sqlAttempts: res.sql_attempts,
                  tokens: res.input_tokens + res.output_tokens,
                }))
                break
              }
              case 'error':
                patch(id, (r) => ({ ...r, status: 'failed', error: event.data.error }))
                break
            }
          },
          abort.signal,
        )
        patch(id, (r) => (r.status === 'running' ? { ...r, status: 'failed', error: 'The stream ended early.' } : r))
      } catch (err) {
        const message = abort.signal.aborted
          ? 'Stopped.'
          : err instanceof Error
            ? `Could not reach the API: ${err.message}`
            : 'Something went wrong.'
        patch(id, (r) => ({ ...r, status: 'failed', error: message }))
      } finally {
        if (controller.current === abort) controller.current = null
        onFinished?.()
      }
    },
    [onFinished],
  )

  const stop = useCallback(() => controller.current?.abort(), [])
  const busy = turns.some((t) => t.status === 'running')
  const reset = useCallback(() => setTurns([]), [])

  return { turns, ask, stop, busy, reset }
}
