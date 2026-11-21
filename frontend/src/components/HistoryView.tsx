import { ArrowLeft, History, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { formatDuration, timeAgo } from '../lib/format'
import type { RunDetail, RunSummary } from '../types'
import { RunView, type RunViewModel } from './RunView'

function toViewModel(run: RunDetail): RunViewModel {
  return {
    id: run.id,
    question: run.question,
    status: run.status,
    answer: run.answer,
    error: run.error,
    sql: run.sql,
    columns: run.columns,
    rows: run.rows,
    truncated: run.truncated,
    steps: run.steps,
    latencyMs: run.latency_ms,
    llmCalls: run.llm_calls,
    sqlAttempts: run.sql_attempts,
    tokens: run.input_tokens + run.output_tokens,
    model: run.model,
  }
}

const dot: Record<RunSummary['status'], string> = {
  succeeded: 'bg-brand-500',
  failed: 'bg-rose-500',
  running: 'bg-amber-400 animate-pulse-dot',
}

interface Props {
  selectedId: string | null
  onSelect: (id: string | null) => void
  refreshKey: number
}

export function HistoryView({ selectedId, onSelect, refreshKey }: Props) {
  const [runs, setRuns] = useState<RunSummary[] | null>(null)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loaded, setLoaded] = useState<{ id: string; run?: RunDetail; error?: string } | null>(null)
  const current = loaded && loaded.id === selectedId ? loaded : null
  const detail = current?.run ?? null
  const detailError = current?.error ?? null

  const [reloads, setReloads] = useState(0)

  useEffect(() => {
    const abort = new AbortController()
    api
      .runs(100, abort.signal)
      .then((res) => {
        setRuns(res.items)
        setTotal(res.total)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!abort.signal.aborted) setError(err instanceof Error ? err.message : 'Failed to load runs')
      })
    return () => abort.abort()
  }, [refreshKey, reloads])

  useEffect(() => {
    if (!selectedId) return
    const abort = new AbortController()
    api
      .run(selectedId, abort.signal)
      .then((run) => setLoaded({ id: selectedId, run }))
      .catch((err: unknown) => {
        if (abort.signal.aborted) return
        setLoaded({ id: selectedId, error: err instanceof Error ? err.message : 'Failed to load run' })
      })
    return () => abort.abort()
  }, [selectedId])

  return (
    <div className="flex h-full min-h-0 flex-col md:flex-row">
      <section
        className={`flex min-h-0 flex-col border-zinc-200 md:w-72 md:shrink-0 md:border-r dark:border-zinc-800 ${selectedId ? 'hidden md:flex' : 'flex'}`}
      >
        <header className="flex items-center justify-between px-5 pt-6 pb-3">
          <div>
            <h1 className="text-base font-semibold tracking-tight">History</h1>
            <p className="text-xs text-zinc-500">
              {total} recorded {total === 1 ? 'run' : 'runs'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setReloads((n) => n + 1)}
            aria-label="Refresh"
            className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-900 dark:hover:text-zinc-100"
          >
            <RefreshCw className="size-4" />
          </button>
        </header>
        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          {error && (
            <p className="m-2 rounded-lg bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
              {error}
            </p>
          )}
          {runs === null && !error && (
            <div className="space-y-2 p-2">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
              ))}
            </div>
          )}
          {runs?.length === 0 && (
            <div className="px-4 py-16 text-center text-sm text-zinc-500">
              <History className="mx-auto mb-3 size-6 text-zinc-300 dark:text-zinc-700" />
              No runs yet. Ask a question and it will show up here with its full trace.
            </div>
          )}
          <ul className="space-y-1">
            {runs?.map((run) => (
              <li key={run.id}>
                <button
                  type="button"
                  onClick={() => onSelect(run.id)}
                  className={`w-full rounded-lg px-3 py-2.5 text-left transition ${
                    run.id === selectedId
                      ? 'bg-white shadow-sm ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800'
                      : 'hover:bg-zinc-100 dark:hover:bg-zinc-900/60'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <span className={`mt-1.5 size-2 shrink-0 rounded-full ${dot[run.status]}`} />
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-2 text-[13px] font-medium text-zinc-800 dark:text-zinc-200">
                        {run.question}
                      </p>
                      <p className="mt-1 flex gap-1.5 font-mono whitespace-nowrap text-[11px] text-zinc-400 tabular-nums">
                        <span>{timeAgo(run.created_at)}</span>
                        <span>·</span>
                        <span>{formatDuration(run.latency_ms)}</span>
                        <span>·</span>
                        <span className="min-w-0 truncate">{run.model}</span>
                      </p>
                    </div>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className={`scrollbar-thin min-h-0 flex-1 overflow-y-auto ${selectedId ? 'block' : 'hidden md:block'}`}>
        {selectedId ? (
          <div className="mx-auto max-w-6xl px-4 py-6 sm:px-8">
            <button
              type="button"
              onClick={() => onSelect(null)}
              className="mb-4 flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-900 md:hidden dark:hover:text-zinc-100"
            >
              <ArrowLeft className="size-4" /> All runs
            </button>
            {detailError && (
              <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
                {detailError}
              </p>
            )}
            {!detail && !detailError && <div className="h-40 animate-pulse rounded-xl bg-zinc-100 dark:bg-zinc-900" />}
            {detail && <RunView key={detail.id} run={toViewModel(detail)} />}
          </div>
        ) : (
          <div className="grid h-full place-items-center p-8 text-center text-sm text-zinc-500">
            <div>
              <History className="mx-auto mb-3 size-7 text-zinc-300 dark:text-zinc-700" />
              Pick a run to see its answer, result and every step of the trace.
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
