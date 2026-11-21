import hljs from 'highlight.js/lib/core'
import sql from 'highlight.js/lib/languages/sql'
import { Check, Copy } from 'lucide-react'
import { useMemo, useState } from 'react'

hljs.registerLanguage('sql', sql)

interface Props {
  code: string
  tone?: 'default' | 'error'
  className?: string
}

export function SqlBlock({ code, tone = 'default', className = '' }: Props) {
  const [copied, setCopied] = useState(false)
  // highlight.js escapes the input, so the generated markup is safe to inject.
  const html = useMemo(() => hljs.highlight(code, { language: 'sql' }).value, [code])

  const copy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1200)
  }

  const border =
    tone === 'error'
      ? 'border-rose-200 dark:border-rose-900/60'
      : 'border-zinc-200 dark:border-zinc-800'

  return (
    <div className={`group relative rounded-lg border bg-zinc-50/80 dark:bg-zinc-900/60 ${border} ${className}`}>
      <pre className="sql-code scrollbar-thin overflow-x-auto px-3.5 py-3 font-mono text-[12.5px] leading-relaxed text-zinc-800 dark:text-zinc-200">
        <code dangerouslySetInnerHTML={{ __html: html }} />
      </pre>
      <button
        type="button"
        onClick={copy}
        aria-label="Copy SQL"
        className="absolute top-2 right-2 rounded-md border border-zinc-200 bg-white/90 p-1.5 text-zinc-500 opacity-0 shadow-sm transition group-hover:opacity-100 hover:text-zinc-900 focus-visible:opacity-100 dark:border-zinc-700 dark:bg-zinc-800/90 dark:hover:text-zinc-100"
      >
        {copied ? <Check className="size-3.5 text-brand-600" /> : <Copy className="size-3.5" />}
      </button>
    </div>
  )
}
