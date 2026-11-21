import { formatCell, isNumeric } from '../lib/format'
import type { Cell } from '../types'

interface Props {
  columns: string[]
  rows: Cell[][]
}

export function ResultTable({ columns, rows }: Props) {
  const numericCols = columns.map((_, i) => rows.length > 0 && rows.every((r) => r[i] === null || isNumeric(r[i])))

  return (
    <div className="scrollbar-thin max-h-[420px] overflow-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full border-collapse text-[13px]">
        <thead className="sticky top-0 z-10 bg-zinc-50/95 backdrop-blur dark:bg-zinc-900/95">
          <tr>
            <th className="w-10 border-b border-zinc-200 px-3 py-2 text-right font-mono text-[11px] font-normal text-zinc-400 dark:border-zinc-800">
              #
            </th>
            {columns.map((col, i) => (
              <th
                key={col + i}
                scope="col"
                className={`border-b border-zinc-200 px-3 py-2 text-[11.5px] font-semibold tracking-wide whitespace-nowrap text-zinc-500 uppercase dark:border-zinc-800 dark:text-zinc-400 ${numericCols[i] ? 'text-right' : 'text-left'}`}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr
              key={r}
              className="odd:bg-white even:bg-zinc-50/60 hover:bg-brand-50/60 dark:odd:bg-zinc-950 dark:even:bg-zinc-900/40 dark:hover:bg-brand-950/40"
            >
              <td className="px-3 py-1.5 text-right font-mono text-[11px] text-zinc-400 tabular-nums">{r + 1}</td>
              {row.map((cell, c) => (
                <td
                  key={c}
                  className={`px-3 py-1.5 whitespace-nowrap ${numericCols[c] ? 'text-right font-mono text-[12.5px] tabular-nums' : 'text-left'} ${cell === null ? 'text-zinc-400' : ''}`}
                >
                  {formatCell(cell, columns[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
