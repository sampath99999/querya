import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  Database,
  ListTree,
  Play,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { formatDuration, formatTokens } from '../lib/format'
import type { Step } from '../types'
import { SqlBlock } from './SqlBlock'

interface StepMeta {
  icon: LucideIcon
  title: string
}

function describe(step: Step): StepMeta {
  switch (step.name) {
    case 'list_tables':
      return { icon: ListTree, title: 'Listed tables' }
    case 'describe_table':
      return { icon: Database, title: `Inspected ${String(step.input?.table ?? 'table')}` }
    case 'run_sql':
      return {
        icon: Play,
        title: step.status === 'error' ? 'Query failed' : `Ran query · ${step.row_count ?? 0} rows`,
      }
    case 'final_answer':
      return {
        icon: step.status === 'error' ? AlertTriangle : CheckCircle2,
        title: step.status === 'error' ? 'Answer rejected' : 'Answered',
      }
    case 'model': {
      const calls = toolCalls(step)
      const next = calls.length ? calls.join(', ') : 'reply'
      return { icon: BrainCircuit, title: `Thinking → ${next}` }
    }
    default:
      return { icon: AlertTriangle, title: step.kind === 'error' ? 'Stopped' : step.name }
  }
}

function toolCalls(step: Step): string[] {
  const out = step.output as { tool_calls?: { name: string }[] } | null
  return out?.tool_calls?.map((c) => c.name) ?? []
}

function tone(step: Step): string {
  if (step.status === 'error')
    return 'bg-rose-50 text-rose-600 ring-rose-200 dark:bg-rose-950/50 dark:text-rose-400 dark:ring-rose-900'
  if (step.kind === 'answer')
    return 'bg-brand-50 text-brand-700 ring-brand-200 dark:bg-brand-950 dark:text-brand-300 dark:ring-brand-800'
  if (step.kind === 'llm')
    return 'bg-violet-50 text-violet-600 ring-violet-200 dark:bg-violet-950/50 dark:text-violet-300 dark:ring-violet-900'
  return 'bg-white text-zinc-600 ring-zinc-200 dark:bg-zinc-900 dark:text-zinc-300 dark:ring-zinc-700'
}

function StepDetail({ step }: { step: Step }) {
  if (step.name === 'run_sql') {
    const sql = step.sql ?? String(step.input?.sql ?? '')
    return (
      <div className="space-y-2">
        {sql && <SqlBlock code={sql} tone={step.status === 'error' ? 'error' : 'default'} />}
        {step.status === 'error' && (
          <p className="rounded-md bg-rose-50 px-3 py-2 font-mono text-xs text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
            {String(step.output)}
          </p>
        )}
      </div>
    )
  }
  if (step.kind === 'llm') {
    return step.text ? (
      <p className="text-[13px] leading-relaxed whitespace-pre-wrap text-zinc-600 dark:text-zinc-400">{step.text}</p>
    ) : (
      <p className="text-xs text-zinc-400">No reasoning text returned by the model.</p>
    )
  }
  if (step.kind === 'answer' || step.kind === 'error') {
    return (
      <p className="text-[13px] leading-relaxed text-zinc-600 dark:text-zinc-400">
        {step.text ?? String(step.output ?? '')}
      </p>
    )
  }
  return (
    <pre className="scrollbar-thin max-h-56 overflow-auto rounded-md bg-zinc-50 p-3 font-mono text-[11.5px] leading-relaxed whitespace-pre-wrap text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
      {typeof step.output === 'string' ? step.output : JSON.stringify(step.output, null, 2)}
    </pre>
  )
}

function StepRow({ step, last }: { step: Step; last: boolean }) {
  const meta = describe(step)
  const [open, setOpen] = useState(step.name === 'run_sql' || (step.status === 'error' && step.kind !== 'llm'))
  const Icon = meta.icon
  const tokens = formatTokens((step.input_tokens ?? 0) + (step.output_tokens ?? 0))

  return (
    <li className="relative animate-fade-in pl-9">
      {!last && <span className="absolute top-7 bottom-0 left-[13px] w-px bg-zinc-200 dark:bg-zinc-800" aria-hidden />}
      <span className={`absolute top-1 left-0 grid size-7 place-items-center rounded-full ring-1 ${tone(step)}`}>
        <Icon className="size-3.5" strokeWidth={2.2} />
      </span>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-md py-1.5 text-left text-[13px] font-medium text-zinc-800 hover:text-zinc-950 dark:text-zinc-200 dark:hover:text-white"
        aria-expanded={open}
      >
        <ChevronRight className={`size-3.5 shrink-0 text-zinc-400 transition-transform ${open ? 'rotate-90' : ''}`} />
        <span className="min-w-0 flex-1 truncate">{meta.title}</span>
        <span className="flex shrink-0 items-center gap-1.5 font-mono text-[11px] font-normal text-zinc-400 tabular-nums">
          {tokens && <span>{tokens} tok</span>}
          <span>{formatDuration(step.latency_ms)}</span>
        </span>
      </button>
      {open && (
        <div className="animate-fade-in pt-1 pb-3">
          <StepDetail step={step} />
        </div>
      )}
    </li>
  )
}

export function StepTimeline({ steps, running }: { steps: Step[]; running: boolean }) {
  return (
    <ol className="space-y-0.5">
      {steps.map((step, i) => (
        <StepRow key={`${step.index}-${step.name}`} step={step} last={!running && i === steps.length - 1} />
      ))}
      {running && (
        <li className="relative pl-9">
          <span className="absolute top-1 left-0 grid size-7 place-items-center rounded-full bg-white ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-700">
            <span className="size-2 animate-pulse-dot rounded-full bg-brand-500" />
          </span>
          <p className="py-1.5 text-[13px] text-zinc-500">Working…</p>
        </li>
      )}
    </ol>
  )
}
