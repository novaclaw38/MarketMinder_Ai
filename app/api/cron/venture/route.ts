import { NextRequest, NextResponse } from 'next/server'
import { hasServiceSecret } from '../../../../lib/auth'
import { VentureEngine, configFromEnv } from '../../../../lib/venture/engine'
import { SupabaseStore } from '../../../../lib/venture/store'
import { chatJson, llmConfigured } from '../../../../lib/venture/llm'
import { buildChannels } from '../../../../lib/venture/channels'

export const dynamic = 'force-dynamic'
export const maxDuration = 60

export async function GET(request: NextRequest) {
  if (!hasServiceSecret(request)) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (!llmConfigured()) {
    return NextResponse.json({ ok: false, error: 'GROQ_API_KEY is not set; the engine will not launch anything' })
  }

  try {
    const config = configFromEnv()
    const engine = new VentureEngine({ store: new SupabaseStore(), llm: chatJson, channels: buildChannels(), config })
    const result = await engine.tick()
    return NextResponse.json({ ok: true, dry_run: config.dryRun, ...result })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'error' }, { status: 500 })
  }
}
