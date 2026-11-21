import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatCompact } from '../lib/format'
import type { ChartSpec } from '../lib/chart'

const COLORS = ['#129b8c', '#8b5cf6', '#f59e0b']

const axis = { stroke: 'currentColor', fontSize: 11, tickLine: false, axisLine: false } as const

function tooltipFormatter(value: unknown): string {
  return typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value)
}

export function ResultChart({ spec }: { spec: ChartSpec }) {
  const many = spec.data.length > 8
  const common = (
    <>
      <CartesianGrid vertical={false} strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
      <XAxis
        dataKey={spec.label}
        {...axis}
        interval={many ? 'preserveStartEnd' : 0}
        angle={many && spec.type === 'bar' ? -30 : 0}
        textAnchor={many && spec.type === 'bar' ? 'end' : 'middle'}
        height={many && spec.type === 'bar' ? 64 : 30}
        tickFormatter={(v: string) => (v.length > 18 ? `${v.slice(0, 17)}…` : v)}
      />
      <YAxis {...axis} width={56} tickFormatter={(v: number) => formatCompact(v)} />
      <Tooltip
        formatter={tooltipFormatter}
        cursor={{ fill: 'rgb(18 155 140 / 0.08)' }}
        contentStyle={{ borderRadius: 8, border: '1px solid rgb(228 228 231)', fontSize: 12, color: '#18181b' }}
      />
      {spec.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
    </>
  )

  return (
    <div className="h-72 w-full text-zinc-400 dark:text-zinc-500">
      <ResponsiveContainer width="100%" height="100%">
        {spec.type === 'line' ? (
          <LineChart data={spec.data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            {common}
            {spec.series.map((s, i) => (
              <Line
                key={s}
                type="monotone"
                dataKey={s}
                stroke={COLORS[i]}
                strokeWidth={2.2}
                dot={{ r: 2.5 }}
                activeDot={{ r: 4 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        ) : (
          <BarChart data={spec.data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            {common}
            {spec.series.map((s, i) => (
              <Bar key={s} dataKey={s} fill={COLORS[i]} radius={[4, 4, 0, 0]} maxBarSize={48} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}
