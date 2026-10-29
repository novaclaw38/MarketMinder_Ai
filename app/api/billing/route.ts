import { NextRequest, NextResponse } from 'next/server'
import { supabase } from '../../../lib/supabase'
import { requireUser } from '../../../lib/auth'

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const auth = await requireUser(request)
  if (auth.error) return auth.error

  const { data, error } = await supabase
    .from('customers')
    .select('subscription_status, subscription_tier, mrr, current_period_end')
    .eq('email', auth.user.email!)
    .maybeSingle()
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  return NextResponse.json({ subscription: data })
}
