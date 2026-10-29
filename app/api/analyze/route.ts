import { NextRequest, NextResponse } from 'next/server'
import { supabase } from '../../../lib/supabase'
import { processAnalysisRequest } from '../../../lib/analysis'
import { requireUser } from '../../../lib/auth'

export const maxDuration = 60

export async function GET(request: NextRequest) {
  try {
    const { data, error } = await supabase
      .from('health_check')
      .select('*')
      .single()

    if (error) throw error

    return NextResponse.json({
      status: 'ok',
      health: data.health_score || 100,
      timestamp: new Date().toISOString()
    })
  } catch (error: any) {
    return NextResponse.json({ status: 'error', error: error.message ?? 'error' }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  const auth = await requireUser(request)
  if (auth.error) return auth.error

  try {
    const body = await request.json()
    if (!body.query || typeof body.query !== 'string') {
      return NextResponse.json({ error: 'query required' }, { status: 400 })
    }

    const { data, error } = await supabase
      .from('analysis_requests')
      .insert([{
        query: body.query,
        segment: body.segment,
        scope: body.scope,
        user_id: auth.user.id,
        status: 'pending'
      }])
      .select()
      .single()

    if (error) throw error

    // Process inline; the cron job retries anything left pending or stuck
    await processAnalysisRequest(data.id)
    const { data: final } = await supabase
      .from('analysis_requests')
      .select('status, result, error_message')
      .eq('id', data.id)
      .eq('user_id', auth.user.id)
      .single()

    return NextResponse.json({
      success: true,
      request_id: data.id,
      status: final?.status,
      result: final?.result,
      error: final?.error_message
    })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'error' }, { status: 500 })
  }
}