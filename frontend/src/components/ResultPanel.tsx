import { BarChart3, Code2, Download, Table2 } from 'lucide-react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { inferChart } from '../lib/chart'
import { downloadCsv } from '../lib/csv'
import type { Cell } from '../types'
import { ResultTable } from './ResultTable'
import { SqlBlock } from './SqlBlock'

const ResultChart = lazy(() => import('./ResultChart').then((m) => ({ default: m.ResultChart })))

type Tab = 'chart' | 'table' | 'sql'

interface Props {
  columns: string[]
  rows: Cell[][]
  truncated: boolean
  sql: string | null
  filename: string
}

export function ResultPanel({ columns, rows, truncated, sql, filename }: Props) {
  const chart = useMemo(() => inferChart(columns, rows), [columns, rows])
  const [tab, setTab] = useState<Tab>(chart ? 'chart' : 'table')

  const tabs: { id: Tab; label: string; icon: typeof Table2; show: boolean }[] = [
    { id: 'chart', label: 'Chart', icon: BarChart3, show: chart !== null },
    { id: 'table', label: 'Table', icon: Table2, show: true },
    { id: 'sql', label: 'SQL', icon: Code2, show: Boolean(sql) },
  ]

  return (
    <section className="rounded-xl border border-zinc-200 bg-white shadow-sm shadow-zinc-950/[0.03] dark:border-zinc-800 dark:bg-zinc-950">
      <header className="flex flex-wrap items-center gap-2 border-b border-zinc-100 px-3 py-2 dark:border-zinc-800/80">
        <div role="tablist" className="flex gap-1 rounded-lg bg-zinc-100 p-0.5 dark:bg-zinc-900">
          {tabs
            .filter((t) => t.show)
            .map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                role="tab"
                type="button"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition ${
                  tab === id
                    ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100'
                    : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                }`}
              >
                <Icon className="size-3.5" />
                {label}
              </button>
            ))}
        </div>
        <span className="ml-auto text-xs text-zinc-500 tabular-nums">
          {rows.length.toLocaleString()} {rows.length === 1 ? 'row' : 'rows'}
          {truncated && ' · limited'}
        </span>
        <button
          type="button"
          onClick={() => downloadCsv(filename, columns, rows)}
          disabled={rows.length === 0}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 disabled:opacity-40 dark:hover:bg-zinc-900 dark:hover:text-zinc-100"
        >
          <Download className="size-3.5" />
          CSV
        </button>
      </header>
      <div className="p-3">
        {rows.length === 0 && tab !== 'sql' ? (
          <p className="py-10 text-center text-sm text-zinc-500">The query returned no rows.</p>
        ) : tab === 'chart' && chart ? (
          <Suspense fallback={<div className="h-72 animate-pulse rounded-lg bg-zinc-50 dark:bg-zinc-900" />}>
            <ResultChart spec={chart} />
          </Suspense>
        ) : tab === 'sql' && sql ? (
          <SqlBlock code={sql} />
        ) : (
          <ResultTable columns={columns} rows={rows} />
        )}
      </div>
    </section>
  )
}
