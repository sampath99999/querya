import { useEffect, useRef } from 'react'
import type { useAsk } from '../hooks/useAsk'
import { Composer } from './Composer'
import { EmptyState } from './EmptyState'
import { RunView } from './RunView'

type AskState = ReturnType<typeof useAsk>

export function AskView({ state }: { state: AskState }) {
  const { turns, ask, stop, busy } = state
  const endRef = useRef<HTMLDivElement>(null)
  const lastCount = useRef(0)

  useEffect(() => {
    if (turns.length > lastCount.current) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    lastCount.current = turns.length
  }, [turns.length])

  return (
    <div className="flex min-h-full flex-col">
      <div className="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 pb-8 sm:px-8">
        {turns.length === 0 ? (
          <EmptyState onPick={ask} />
        ) : (
          <div className="space-y-10">
            {turns.map((turn, i) => (
              <div key={turn.id} className={i > 0 ? 'border-t border-zinc-200 pt-10 dark:border-zinc-800' : ''}>
                <RunView run={turn} />
              </div>
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="sticky bottom-0 bg-gradient-to-t from-zinc-50 via-zinc-50/95 to-transparent px-4 pt-6 pb-4 sm:px-8 dark:from-zinc-950 dark:via-zinc-950/95">
        <div className="mx-auto max-w-3xl">
          <Composer busy={busy} onSubmit={ask} onStop={stop} autoFocus />
          <p className="mt-2 text-center text-[11px] text-zinc-400">
            Read-only access. Every query is checked before it runs and is limited in rows and time.
          </p>
        </div>
      </div>
    </div>
  )
}
