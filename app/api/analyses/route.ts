import { NextRequest, NextResponse } from 'next/server'
import { supabase } from '../../../lib/supabase'
import { requireUser } from '../../../lib/auth'

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const auth = await requireUser(request)
  if (auth.error) return auth.error

  const { data, error } = await supabase
    .from('analysis_requests')
    .select('id, query, segment, status, result, error_message, created_at')
    .eq('user_id', auth.user.id)
    .order('created_at', { ascending: false })
    .limit(10)
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  return NextResponse.json({ analyses: data })
}
