import { NextRequest, NextResponse } from 'next/server'
import { supabase } from '../../../lib/supabase'
import { requireUser } from '../../../lib/auth'

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const auth = await requireUser(request)
  if (auth.error) return auth.error

  try {
    const [divisions, pnl, agents, activity, products] = await Promise.all([
      supabase.from('divisions').select('*').order('started_at', { ascending: false }),
      supabase.from('division_pnl').select('*'),
      supabase.from('division_agents').select('*').neq('status', 'retired'),
      supabase.from('activity_log').select('*').order('created_at', { ascending: false }).limit(200),
      supabase.from('products').select('division_id, slug, title, price_cents, currency').eq('status', 'published')
    ])
    for (const r of [divisions, pnl, agents, activity, products]) if (r.error) throw r.error

    const result = (divisions.data ?? []).map((d) => ({
      ...d,
      pnl: pnl.data?.find((p) => p.division_id === d.id),
      agents: agents.data?.filter((a) => a.division_id === d.id) ?? [],
      products: products.data?.filter((p) => p.division_id === d.id) ?? [],
      activity: activity.data?.filter((a) => a.division_id === d.id).slice(0, 8) ?? []
    }))
    return NextResponse.json({ divisions: result })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'error' }, { status: 500 })
  }
}
