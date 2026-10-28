import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)

export async function GET() {
  try {
    // Get metrics from Supabase
    const [
      { data: mrrData, error: mrrError },
      { data: churnData, error: churnError },
      { data: healthData, error: healthError },
      { data: agentData, error: agentError }
    ] = await Promise.all([
      supabase.from('metrics').select('*').eq('metric_name', 'mrr').single(),
      supabase.from('metrics').select('*').eq('metric_name', 'churn_rate').single(),
      supabase.from('health_check').select('*').single(),
      supabase.from('agent_status').select('*')
    ])

    const metrics = {
      mrr: mrrData?.value || 0,
      churn_rate: churnData?.value || 0,
      health_score: healthData?.health_score || 100,
      cash_runway: healthData?.cash_runway_days || 90,
      agents: agentData || [],
      last_updated: new Date().toISOString()
    }

    return NextResponse.json(metrics)
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'error' }, { status: 500 })
  }
}