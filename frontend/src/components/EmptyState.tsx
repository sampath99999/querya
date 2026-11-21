import { ArrowUpRight } from 'lucide-react'
import { SUGGESTIONS } from '../lib/suggestions'

export function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="mx-auto max-w-2xl animate-fade-in py-10 text-center sm:py-16">
      <p className="text-xs font-semibold tracking-[0.18em] text-brand-700 uppercase dark:text-brand-400">
        Retail sales · 2024–2025
      </p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight text-balance text-zinc-900 sm:text-4xl dark:text-zinc-50">
        Ask the database a question in plain English
      </h1>
      <p className="mx-auto mt-3 max-w-lg text-[15px] leading-relaxed text-balance text-zinc-500 dark:text-zinc-400">
        Querya writes the SQL, runs it on a read-only connection, fixes its own mistakes and shows every step it took.
      </p>
      <div className="mt-8 grid gap-2 text-left sm:grid-cols-2">
        {SUGGESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onPick(q)}
            className="group flex items-start justify-between gap-3 rounded-xl text-left border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700 transition hover:-translate-y-px hover:border-brand-300 hover:shadow-md hover:shadow-brand-900/5 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-brand-700"
          >
            <span>{q}</span>
            <ArrowUpRight className="mt-0.5 size-4 shrink-0 text-zinc-300 transition group-hover:text-brand-600 dark:text-zinc-600" />
          </button>
        ))}
      </div>
    </div>
  )
}
