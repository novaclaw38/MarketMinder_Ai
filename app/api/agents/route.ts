import { NextRequest, NextResponse } from 'next/server'
import { supabase } from '../../../lib/supabase'
import { requireUser, hasServiceSecret } from '../../../lib/auth'

export const dynamic = 'force-dynamic'

// Agent registry
const AGENTS = {
  'market_scout': 'Market Scout',
  'product_builder': 'Product Builder',
  'finance_controller': 'Finance Controller',
  'marketing_engine': 'Marketing Engine',
  'customer_success': 'Customer Success',
  'sales_closer': 'Sales Closer'
}

export async function GET(request: NextRequest) {
  if (!hasServiceSecret(request)) {
    const auth = await requireUser(request)
    if (auth.error) return auth.error
  }

  try {
    const searchParams = request.nextUrl.searchParams
    const agent = searchParams.get('agent')

    let query = supabase.from('agent_status').select('*')
    
    if (agent && agent !== 'all') {
      query = query.eq('agent_name', agent)
    }

    const { data, error } = await query.order('last_updated', { ascending: false })

    if (error) throw error

    // Build agent status map
    const agentStatus: Record<string, any> = {}
    const now = new Date().toISOString()

    Object.keys(AGENTS).forEach((agentName) => {
      const agentData = data?.find((a: any) => a.agent_name === agentName)
      agentStatus[agentName] = agentData || {
        agent_name: agentName,
        status: 'idle',
        last_updated: now,
        tasks_completed: 0,
        error_count: 0
      }
    })

    return NextResponse.json({
      agents: agentStatus,
      timestamp: now
    })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'error' }, { status: 500 })
  }
}

// Changing agent state is restricted to machine callers
export async function POST(request: NextRequest) {
  if (!hasServiceSecret(request)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    const body = await request.json()
    const { agent_name, action, data } = body

    if (!agent_name || !action) {
      return NextResponse.json({ error: 'agent_name and action required' }, { status: 400 })
    }

    if (!AGENTS[agent_name as keyof typeof AGENTS]) {
      return NextResponse.json({ error: `Unknown agent: ${agent_name}` }, { status: 400 })
    }

    // Update agent status
    const { data: updated, error } = await supabase
      .from('agent_status')
      .upsert([{
        agent_name,
        status: action,
        last_updated: new Date().toISOString(),
        ...(data ? { data } : {})
      }], { onConflict: 'agent_name' })
      .select()
      .single()

    if (error) throw error

    return NextResponse.json({
      success: true,
      agent: updated
    })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'error' }, { status: 500 })
  }
}