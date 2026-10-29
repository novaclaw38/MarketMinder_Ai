import { supabase } from './supabase'

// Groq (OpenAI-compatible) is preferred; OpenAI is the fallback
function provider() {
  if (process.env.GROQ_API_KEY) {
    return {
      url: 'https://api.groq.com/openai/v1/chat/completions',
      key: process.env.GROQ_API_KEY,
      model: process.env.GROQ_MODEL || 'llama-3.3-70b-versatile'
    }
  }
  if (process.env.OPENAI_API_KEY) {
    return {
      url: 'https://api.openai.com/v1/chat/completions',
      key: process.env.OPENAI_API_KEY,
      model: process.env.OPENAI_MODEL || 'gpt-4o-mini'
    }
  }
  return null
}

interface AnalysisRequest {
  id: string
  query: string | null
  segment: string | null
  scope: string | null
}

async function generateAnalysis(req: AnalysisRequest) {
  const llm = provider()
  if (!llm) {
    return {
      result: {
        summary: 'GROQ_API_KEY not configured; no AI analysis was generated.',
        query: req.query,
        segment: req.segment,
        generated_by: 'fallback'
      },
      tokens: 0
    }
  }

  const res = await fetch(llm.url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${llm.key}` },
    body: JSON.stringify({
      model: llm.model,
      response_format: { type: 'json_object' },
      messages: [
        {
          role: 'system',
          content:
            'You are a market analyst. Reply with JSON: {"summary": string, "opportunities": string[], "risks": string[], "next_steps": string[]}.'
        },
        {
          role: 'user',
          content: `Query: ${req.query ?? ''}\nSegment: ${req.segment ?? 'general'}\nScope: ${req.scope ?? 'default'}`
        }
      ]
    })
  })
  if (!res.ok) throw new Error(`LLM request failed: ${res.status}`)

  const json = await res.json()
  const content = json.choices?.[0]?.message?.content
  return {
    result: { ...JSON.parse(content), generated_by: llm.model },
    tokens: json.usage?.total_tokens ?? 0
  }
}

// Claims a request (pending -> processing) and completes or fails it.
// Returns false if another worker already claimed it.
export async function processAnalysisRequest(id: string): Promise<boolean> {
  const { data: claimed } = await supabase
    .from('analysis_requests')
    .update({ status: 'processing', updated_at: new Date().toISOString() })
    .eq('id', id)
    .eq('status', 'pending')
    .select()
    .maybeSingle()
  if (!claimed) return false

  try {
    const { result, tokens } = await generateAnalysis(claimed)
    await supabase
      .from('analysis_requests')
      .update({
        status: 'completed',
        result,
        tokens_used: tokens,
        completed_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .eq('id', id)
  } catch (e: any) {
    await supabase
      .from('analysis_requests')
      .update({
        status: 'failed',
        error_message: e.message ?? 'error',
        updated_at: new Date().toISOString()
      })
      .eq('id', id)
  }
  return true
}
