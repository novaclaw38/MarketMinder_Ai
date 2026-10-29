// Chat client (Groq preferred, OpenAI fallback) returning parsed JSON plus a cost estimate in cents.

export class LLMUnavailable extends Error {}

export type LLM = (system: string, user: string) => Promise<{ data: any; costCents: number }>

// USD per 1M tokens; defaults match llama-3.3-70b-versatile on Groq
const PRICE_IN = Number(process.env.LLM_PRICE_IN_PER_M ?? 0.59)
const PRICE_OUT = Number(process.env.LLM_PRICE_OUT_PER_M ?? 0.79)

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

export const chatJson: LLM = async (system, user) => {
  const p = provider()
  if (!p) throw new LLMUnavailable('GROQ_API_KEY is not set')
  const res = await fetch(p.url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${p.key}` },
    body: JSON.stringify({
      model: p.model,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user }
      ]
    })
  })
  if (!res.ok) throw new Error(`LLM request failed: ${res.status}`)
  const body = await res.json()
  const usage = body.usage ?? {}
  const dollars = ((usage.prompt_tokens ?? 0) * PRICE_IN + (usage.completion_tokens ?? 0) * PRICE_OUT) / 1_000_000
  return {
    data: JSON.parse(body.choices[0].message.content),
    costCents: Math.max(1, Math.ceil(dollars * 100))
  }
}

export const llmConfigured = () => provider() !== null
