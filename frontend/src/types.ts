export type StepKind = 'llm' | 'tool' | 'answer' | 'error'
export type RunStatus = 'running' | 'succeeded' | 'failed'
export type Cell = string | number | boolean | null

export interface Step {
  index: number
  kind: StepKind
  name: string
  status: 'ok' | 'error'
  text: string | null
  input: Record<string, unknown> | null
  output: unknown
  sql: string | null
  row_count: number | null
  latency_ms: number
  input_tokens: number | null
  output_tokens: number | null
  started_at: string
}

export interface AskResult {
  run_id: string
  status: 'succeeded' | 'failed'
  question: string
  answer: string | null
  sql: string | null
  columns: string[]
  rows: Cell[][]
  row_count: number
  truncated: boolean
  error: string | null
  llm_calls: number
  sql_attempts: number
  input_tokens: number
  output_tokens: number
  latency_ms: number
}

export interface RunSummary {
  id: string
  question: string
  status: RunStatus
  answer: string | null
  row_count: number
  provider: string
  model: string
  llm_calls: number
  sql_attempts: number
  input_tokens: number
  output_tokens: number
  latency_ms: number
  created_at: string
}

export interface RunDetail extends RunSummary {
  sql: string | null
  columns: string[]
  rows: Cell[][]
  truncated: boolean
  error: string | null
  finished_at: string | null
  steps: Step[]
}

export interface Health {
  status: string
  database: string
  tables: number
  provider: string
  model: string
}

export interface ColumnInfo {
  name: string
  type: string
  nullable: boolean
  primary_key: boolean
}

export interface TableDetail {
  name: string
  row_count: number
  columns: ColumnInfo[]
  foreign_keys: { columns: string[]; references_table: string; references_columns: string[] }[]
  sample_rows: Record<string, Cell>[]
}

export interface SchemaResponse {
  dialect: string
  tables: TableDetail[]
}

export type AskEvent =
  | { event: 'run'; data: { run_id: string; question: string; provider: string; model: string } }
  | { event: 'step'; data: Step }
  | { event: 'result'; data: AskResult }
  | { event: 'error'; data: { run_id: string; error: string } }
