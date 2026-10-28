// Cron job for agent orchestration
// Deploy to Vercel Edge Functions with scheduled triggers

import { NextRequest, NextResponse } from 'next/server'

// Run every 5 minutes
export const revalidate = 300

// Agent configurations
const AGENTS = [
  { name: 'market_scout', schedule: '*/15 * * * *' },      // Every 15 min
  { name: 'product_builder', schedule: '*/30 * * * *' },    // Every 30 min
  { name: 'finance_controller', schedule: '0 * * * *' },     // Every hour
  { name: 'marketing_engine', schedule: '*/10 * * * *' },   // Every 10 min
  { name: 'customer_success', schedule: '*/5 * * * *' },   // Every 5 min
  { name: 'sales_closer', schedule: '0,30 * * * *' }       // Every 30 min
]

export async function GET(request: NextRequest) {
  const authHeader = request.headers.get('authorization')
  
  // Verify cron secret (set in VERCEL environment)
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  )

  const results = []

  // Check each agent based on their schedule
  for (const agent of AGENTS) {
    const now = new Date()
    const hour = now.getUTCHours()
    const minute = now.getUTCMinutes()

    // Check if it's time to run this agent
    let shouldRun = false
    
    switch (agent.name) {
      case 'market_scout':
        shouldRun = minute % 15 === 0
        break
      case 'product_builder':
        shouldRun = minute % 30 === 0
        break
      case 'finance_controller':
        shouldRun = minute === 0
        break
      case 'marketing_engine':
        shouldRun = minute % 10 === 0
        break
      case 'customer_success':
        shouldRun = minute % 5 === 0
        break
      case 'sales_closer':
        shouldRun = minute === 0 || minute === 30
        break
    }

    if (shouldRun) {
      // Update agent status
      await supabase
        .from('agent_status')
        .update({
          status: 'processing',
          last_updated: new Date().toISOString()
        })
        .eq('agent_name', agent.name)
        .execute()

      // Trigger agent (calling external Python worker or edge function)
      // This is a placeholder - implement actual agent logic
      results.push({
        agent: agent.name,
        started: new Date().toISOString(),
        status: 'processing'
      })
    }
  }

  // Update health metrics
  const { data: metrics } = await supabase
    .from('metrics')
    .select('*')

  const mrr = metrics?.find(m => m.metric_name === 'mrr')?.value || 0
  const churn = metrics?.find(m => m.metric_name === 'churn_rate')?.value || 0
  const cash = metrics?.find(m => m.metric_name === 'cash_runway_days')?.value || 90

  // Calculate health score
  const healthScore = calculateHealthScore(mrr, churn, cash)

  await supabase
    .from('health_check')
    .update({
      health_score: healthScore,
      last_updated: new Date().toISOString()
    })
    .eq('id', 1)
    .execute()

  return NextResponse.json({
    success: true,
    timestamp: new Date().toISOString(),
    agents_triggered: results,
    health_score: healthScore
  })
}

function calculateHealthScore(mrr: number, churn: number, cash: number): number {
  const mrrScore = Math.min(100, (mrr / 5000) * 100)
  const churnScore = Math.max(0, 100 - (churn * 100))
  const cashScore = Math.min(100, (cash / 90) * 100)
  
  return Math.round((mrrScore * 0.3 + churnScore * 0.25 + cashScore * 0.45))
}