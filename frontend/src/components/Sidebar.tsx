import { ChevronRight, History, KeyRound, MessageSquareText, Plus, Table2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Health, SchemaResponse, TableDetail } from '../types'

export type View = 'ask' | 'history'

interface Props {
  view: View
  onNavigate: (view: View) => void
  onNewChat: () => void
}

function TableItem({ table }: { table: TableDetail }) {
  const [open, setOpen] = useState(false)
  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[13px] text-zinc-600 hover:bg-zinc-200/60 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100"
      >
        <ChevronRight className={`size-3 shrink-0 text-zinc-400 transition-transform ${open ? 'rotate-90' : ''}`} />
        <Table2 className="size-3.5 shrink-0 text-zinc-400" />
        <span className="flex-1 truncate font-mono text-[12px]">{table.name}</span>
        <span className="font-mono text-[10.5px] text-zinc-400 tabular-nums">{table.row_count.toLocaleString()}</span>
      </button>
      {open && (
        <ul className="mt-0.5 mb-1.5 ml-[26px] space-y-px border-l border-zinc-200 pl-2.5 dark:border-zinc-800">
          {table.columns.map((c) => (
            <li key={c.name} className="flex items-center gap-1.5 py-0.5 font-mono text-[11.5px] text-zinc-500">
              {c.primary_key && <KeyRound className="size-2.5 text-amber-500" />}
              <span className="truncate text-zinc-700 dark:text-zinc-300">{c.name}</span>
              <span className="ml-auto truncate text-[10.5px] text-zinc-400 lowercase">{c.type}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

export function Sidebar({ view, onNavigate, onNewChat }: Props) {
  const [health, setHealth] = useState<Health | null>(null)
  const [schema, setSchema] = useState<SchemaResponse | null>(null)
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    const abort = new AbortController()
    Promise.all([api.health(abort.signal), api.schema(abort.signal)])
      .then(([h, s]) => {
        setHealth(h)
        setSchema(s)
      })
      .catch(() => {
        if (!abort.signal.aborted) setOffline(true)
      })
    return () => abort.abort()
  }, [])

  const nav: { id: View; label: string; icon: typeof History }[] = [
    { id: 'ask', label: 'Ask', icon: MessageSquareText },
    { id: 'history', label: 'History', icon: History },
  ]

  return (
    <aside className="flex shrink-0 flex-col border-zinc-200 bg-zinc-100/70 md:h-full md:w-64 md:border-r dark:border-zinc-800 dark:bg-zinc-900/40">
      <div className="flex items-center gap-2.5 px-4 py-3 md:px-5 md:pt-5 md:pb-4">
        <div className="grid size-8 place-items-center rounded-lg bg-brand-600 text-white shadow-sm shadow-brand-900/20">
          <svg viewBox="0 0 32 32" className="size-5" aria-hidden>
            <path d="M8 10h16M8 16h11M8 22h6" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" />
          </svg>
        </div>
        <div className="leading-tight">
          <p className="text-[15px] font-semibold tracking-tight">Querya</p>
          <p className="text-[11px] text-zinc-500">SQL analyst agent</p>
        </div>
        <button
          type="button"
          onClick={onNewChat}
          aria-label="New question"
          className="ml-auto rounded-md p-1.5 text-zinc-500 hover:bg-zinc-200/70 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
        >
          <Plus className="size-4" />
        </button>
      </div>

      <nav className="flex gap-1 px-3 pb-3 md:flex-col md:pb-4">
        {nav.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => onNavigate(id)}
            aria-current={view === id ? 'page' : undefined}
            className={`flex flex-1 items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition md:flex-none ${
              view === id
                ? 'bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-50 dark:ring-zinc-700'
                : 'text-zinc-600 hover:bg-zinc-200/60 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100'
            }`}
          >
            <Icon className="size-4" />
            {label}
          </button>
        ))}
      </nav>

      <div className="scrollbar-thin hidden min-h-0 flex-1 overflow-y-auto px-3 md:block">
        <p className="px-2 pb-1.5 text-[10.5px] font-semibold tracking-wider text-zinc-400 uppercase">Schema</p>
        {schema ? (
          <ul>
            {schema.tables.map((t) => (
              <TableItem key={t.name} table={t} />
            ))}
          </ul>
        ) : (
          <div className="space-y-1.5 px-2">
            {offline ? (
              <p className="text-xs text-zinc-500">Schema unavailable.</p>
            ) : (
              [0, 1, 2, 3, 4].map((i) => (
                <div key={i} className="h-5 animate-pulse rounded bg-zinc-200/70 dark:bg-zinc-800" />
              ))
            )}
          </div>
        )}
      </div>

      <div className="hidden border-t border-zinc-200 px-5 py-3 md:block dark:border-zinc-800">
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`size-2 rounded-full ${health ? 'bg-emerald-500' : offline ? 'bg-rose-500' : 'bg-zinc-300'}`}
          />
          <span className="font-medium text-zinc-700 dark:text-zinc-300">
            {health ? `${health.database} · ${health.tables} tables` : offline ? 'API offline' : 'Connecting…'}
          </span>
        </div>
        {health && (
          <p
            className="mt-1 truncate pl-4 font-mono text-[11px] text-zinc-500"
            title={`${health.provider}/${health.model}`}
          >
            {health.model}
          </p>
        )}
      </div>
    </aside>
  )
}
