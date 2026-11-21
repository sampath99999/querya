import { AlertCircle, Clock, Cpu, Hash, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'
import { formatDuration, formatTokens } from '../lib/format'
import type { Cell, Step } from '../types'
import { ResultPanel } from './ResultPanel'
import { StepTimeline } from './StepTimeline'

export interface RunViewModel {
  id: string
  question: string
  status: 'running' | 'succeeded' | 'failed'
  answer: string | null
  error: string | null
  sql: string | null
  columns: string[]
  rows: Cell[][]
  truncated: boolean
  steps: Step[]
  latencyMs: number | null
  llmCalls: number
  sqlAttempts: number
  tokens: number
  model: string | null
}

function Metric({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-0.5 text-[11.5px] font-medium text-zinc-600 tabular-nums dark:bg-zinc-900 dark:text-zinc-400">
      {icon}
      {children}
    </span>
  )
}

function AnswerCard({ run }: { run: RunViewModel }) {
  if (run.status === 'running') {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-center gap-2 text-sm text-zinc-500">
          <span className="size-2 animate-pulse-dot rounded-full bg-brand-500" />
          Working on it. Steps appear on the right as the agent runs.
        </div>
        <div className="mt-4 space-y-2">
          <div className="h-3 w-3/4 animate-pulse rounded bg-zinc-100 dark:bg-zinc-900" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-zinc-100 dark:bg-zinc-900" />
        </div>
      </div>
    )
  }
  if (run.status === 'failed') {
    return (
      <div className="flex gap-3 rounded-xl border border-rose-200 bg-rose-50/70 p-4 text-sm text-rose-800 dark:border-rose-900/70 dark:bg-rose-950/30 dark:text-rose-200">
        <AlertCircle className="mt-0.5 size-4 shrink-0" />
        <div>
          <p className="font-medium">No answer this time</p>
          <p className="mt-0.5 text-rose-700/90 dark:text-rose-300/90">{run.error ?? 'The agent stopped early.'}</p>
        </div>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-brand-200/70 bg-gradient-to-b from-brand-50/80 to-white p-5 dark:border-brand-900/70 dark:from-brand-950/60 dark:to-zinc-950">
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-brand-700 uppercase dark:text-brand-300">
        <Sparkles className="size-3.5" />
        Answer
      </div>
      <p className="text-[15px] leading-relaxed text-zinc-900 dark:text-zinc-100">{run.answer}</p>
    </div>
  )
}

export function RunView({ run }: { run: RunViewModel }) {
  const done = run.status !== 'running'
  const hasResult = run.columns.length > 0
  const tokens = formatTokens(run.tokens)

  return (
    <article className="grid animate-fade-in gap-5 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-4">
        <div className="flex items-start gap-3">
          <div className="grid size-8 shrink-0 place-items-center rounded-full bg-zinc-900 text-xs font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
            Q
          </div>
          <div className="min-w-0 pt-1">
            <h2 className="text-[17px] font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{run.question}</h2>
            {done && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {run.latencyMs !== null && <Metric icon={<Clock className="size-3" />}>{formatDuration(run.latencyMs)}</Metric>}
                <Metric icon={<Cpu className="size-3" />}>
                  {run.llmCalls} model {run.llmCalls === 1 ? 'call' : 'calls'}
                </Metric>
                <Metric icon={<Hash className="size-3" />}>
                  {run.sqlAttempts} SQL {run.sqlAttempts === 1 ? 'attempt' : 'attempts'}
                </Metric>
                {tokens && <Metric icon={<span className="font-mono text-[10px]">T</span>}>{tokens} tokens</Metric>}
                {run.model && <Metric icon={null}>{run.model}</Metric>}
              </div>
            )}
          </div>
        </div>
        <AnswerCard run={run} />
        {hasResult && (
          <ResultPanel
            key={run.id}
            columns={run.columns}
            rows={run.rows}
            truncated={run.truncated}
            sql={run.sql}
            filename={`querya-${run.id.slice(0, 8)}.csv`}
          />
        )}
      </div>
      <aside className="min-w-0 lg:border-l lg:border-zinc-200 lg:pl-5 dark:lg:border-zinc-800">
        <h3 className="mb-3 flex items-center justify-between text-[11px] font-semibold tracking-wider text-zinc-500 uppercase">
          Trace
          <span className="font-mono font-normal normal-case">{run.steps.length} steps</span>
        </h3>
        <StepTimeline steps={run.steps} running={!done} />
      </aside>
    </article>
  )
}
