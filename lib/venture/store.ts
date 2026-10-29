import { supabase } from '../supabase'

// Filters use PostgREST syntax: { status: 'eq.active', created_at: 'gte.2026-01-01' }
export type Filters = Record<string, string>
export type Row = Record<string, any>

export interface Pnl {
  revenue_cents: number
  refund_cents: number
  cost_cents: number
  profit_cents: number
}

export interface Store {
  select(table: string, filters?: Filters, opts?: { limit?: number; order?: string; columns?: string }): Promise<Row[]>
  insert(table: string, row: Row): Promise<Row>
  patch(table: string, match: Filters, values: Row): Promise<void>
  pnl(divisionId: string): Promise<Pnl>
}

const EMPTY: Pnl = { revenue_cents: 0, refund_cents: 0, cost_cents: 0, profit_cents: 0 }

export class SupabaseStore implements Store {
  private apply(q: any, filters: Filters) {
    for (const [col, spec] of Object.entries(filters)) {
      const i = spec.indexOf('.')
      const op = spec.slice(0, i)
      const val = spec.slice(i + 1)
      if (op === 'eq') q = q.eq(col, val)
      else if (op === 'neq') q = q.neq(col, val)
      else if (op === 'gte') q = q.gte(col, val)
      else throw new Error(`unsupported filter op ${op}`)
    }
    return q
  }

  async select(table: string, filters: Filters = {}, opts: { limit?: number; order?: string; columns?: string } = {}) {
    let q = this.apply(supabase.from(table).select(opts.columns ?? '*'), filters)
    if (opts.order) {
      const [col, dir] = opts.order.split('.')
      q = q.order(col, { ascending: dir !== 'desc' })
    }
    if (opts.limit) q = q.limit(opts.limit)
    const { data, error } = await q
    if (error) throw error
    return data ?? []
  }

  async insert(table: string, row: Row) {
    const { data, error } = await supabase.from(table).insert(row).select().single()
    if (error) throw error
    return data
  }

  async patch(table: string, match: Filters, values: Row) {
    const { error } = await this.apply(supabase.from(table).update(values), match)
    if (error) throw error
  }

  async pnl(divisionId: string) {
    const rows = await this.select('division_pnl', { division_id: `eq.${divisionId}` })
    return (rows[0] as Pnl) ?? EMPTY
  }
}
