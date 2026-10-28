import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)

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
  } catch (error) {
    return NextResponse.json({ status: 'error', error: error.message }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    // Save analysis request to Supabase
    const { data, error } = await supabase
      .from('analysis_requests')
      .insert([{
        ...body,
        created_at: new Date().toISOString(),
        status: 'processing'
  }])
      .select()
      .single()

    if (error) throw error

    return NextResponse.json({
      success: true,
      request_id: data.id,
      message: 'Analysis request received'
    })
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
}