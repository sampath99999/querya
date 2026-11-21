import { ArrowUp, Square } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

interface Props {
  busy: boolean
  onSubmit: (question: string) => void
  onStop: () => void
  autoFocus?: boolean
}

export function Composer({ busy, onSubmit, onStop, autoFocus = false }: Props) {
  const [value, setValue] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [value])

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    const question = value.trim()
    if (question.length < 3 || busy) return
    onSubmit(question)
    setValue('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) submit(e)
  }

  return (
    <form
      onSubmit={submit}
      className="flex items-end gap-2 rounded-2xl border border-zinc-200 bg-white p-2 pl-4 shadow-lg shadow-zinc-950/5 transition focus-within:border-brand-400 focus-within:ring-4 focus-within:ring-brand-500/10 dark:border-zinc-800 dark:bg-zinc-900 dark:shadow-black/30"
    >
      <label htmlFor="question" className="sr-only">
        Ask a question about the data
      </label>
      <textarea
        id="question"
        ref={ref}
        rows={1}
        value={value}
        autoFocus={autoFocus}
        maxLength={500}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask about revenue, customers, products, payments…"
        className="max-h-40 min-h-[28px] flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-6 text-zinc-900 outline-none placeholder:text-zinc-400 dark:text-zinc-100"
      />
      {busy ? (
        <button
          type="button"
          onClick={onStop}
          aria-label="Stop"
          className="grid size-9 shrink-0 place-items-center rounded-xl bg-zinc-900 text-white transition hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
        >
          <Square className="size-3.5 fill-current" />
        </button>
      ) : (
        <button
          type="submit"
          aria-label="Ask"
          disabled={value.trim().length < 3}
          className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand-600 text-white transition hover:bg-brand-700 disabled:bg-zinc-200 disabled:text-zinc-400 dark:disabled:bg-zinc-800 dark:disabled:text-zinc-600"
        >
          <ArrowUp className="size-4" strokeWidth={2.5} />
        </button>
      )}
    </form>
  )
}
