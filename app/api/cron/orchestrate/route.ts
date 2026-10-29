import { NextRequest, NextResponse } from 'next/server'
import { supabase } from '../../../../lib/supabase'
import { processAnalysisRequest } from '../../../../lib/analysis'

export const dynamic = 'force-dynamic'
export const maxDuration = 60

const BATCH_SIZE = 5
const STALE_MINUTES = 10

export async function GET(request: NextRequest) {
  const authHeader = request.headers.get('authorization')

  if (!process.env.CRON_SECRET || authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    // Requeue requests stuck in processing (e.g. a crashed invocation)
    const staleBefore = new Date(Date.now() - STALE_MINUTES * 60_000).toISOString()
    await supabase
      .from('analysis_requests')
      .update({ status: 'pending' })
      .eq('status', 'processing')
      .lt('updated_at', staleBefore)

    const { data: pending, error } = await supabase
      .from('analysis_requests')
      .select('id')
      .eq('status', 'pending')
      .order('created_at', { ascending: true })
      .limit(BATCH_SIZE)
    if (error) throw error

    let processed = 0
    for (const row of pending ?? []) {
      if (await processAnalysisRequest(row.id)) processed++
    }

    // Record market_scout activity
    const { data: scout } = await supabase
      .from('agent_status')
      .select('tasks_completed')
      .eq('agent_name', 'market_scout')
      .maybeSingle()
    await supabase.from('agent_status').upsert(
      {
        agent_name: 'market_scout',
        status: 'idle',
        last_updated: new Date().toISOString(),
        tasks_completed: (scout?.tasks_completed ?? 0) + processed
      },
      { onConflict: 'agent_name' }
    )

    // Refresh health summary from agent error rates
    const { data: agents } = await supabase.from('agent_status').select('tasks_completed,error_count')
    const tasks = (agents ?? []).reduce((s, a) => s + (a.tasks_completed ?? 0), 0)
    const errors = (agents ?? []).reduce((s, a) => s + (a.error_count ?? 0), 0)
    const healthScore = tasks > 0 ? Math.max(0, 100 - (errors / tasks) * 100) : 100
    await supabase
      .from('health_check')
      .update({ health_score: healthScore, last_updated: new Date().toISOString() })
      .eq('id', 1)

    return NextResponse.json({
      success: true,
      processed,
      health_score: healthScore,
      timestamp: new Date().toISOString()
    })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'error' }, { status: 500 })
  }
}
