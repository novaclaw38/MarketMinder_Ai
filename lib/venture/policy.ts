// Hard guardrails for the autonomous venture engine. Enforced in code; agents cannot waive them
// and no human approval is needed or consulted.

export const MIN_PRICE_CENTS = 300
export const MAX_PRICE_CENTS = 20_000

// Categories the engine will never launch (illegal, regulated, or harmful by default)
const FORBIDDEN = [
  /\bgambl/, /\bbetting\b/, /\bcasino/, /\bporn/, /\badult\b/, /\bescort/,
  /\bcrypto (signal|trading|pump)/, /\bforex signal/, /\binvestment advice/, /\bfinancial advice/,
  /\bmedical advice/, /\bdiagnos/, /\blegal advice/, /\bweight loss/, /\bsupplement/,
  /\bfake (review|testimonial|follower)/, /\bscrap\w* (emails?|phone|personal)/, /\blead list/,
  /\bspam/, /\bcold (email|dm|outreach)/, /\bessay writing/, /\bhomework/, /\bimperson/,
  /\bget[- ]rich/, /\bmlm\b/, /\bpyramid/, /\bhack/, /\bcracked?\b/, /\bcounterfeit/
]

// What agents may do. Anything else is rejected, including money movement and unsolicited contact.
const ALLOWED_ACTIONS = new Set([
  'research', 'create_product', 'publish_article', 'review_content', 'spawn_agent', 'log', 'distribute_post'
])

export type Screen = { ok: true } | { ok: false; reason: string }

export function screenText(text: string): Screen {
  const lowered = text.toLowerCase()
  for (const pattern of FORBIDDEN) {
    if (pattern.test(lowered)) return { ok: false, reason: `matches forbidden category: ${pattern.source}` }
  }
  return { ok: true }
}

export interface Idea {
  name: string
  thesis: string
  audience: string
  product_title: string
  price_cents: number
  score?: number
}

export function screenIdea(idea: Partial<Idea>): Screen {
  const required: (keyof Idea)[] = ['name', 'thesis', 'audience', 'product_title', 'price_cents']
  const missing = required.filter((k) => !idea[k])
  if (missing.length) return { ok: false, reason: `missing fields: ${missing.join(', ')}` }
  const price = idea.price_cents!
  if (!Number.isInteger(price) || price < MIN_PRICE_CENTS || price > MAX_PRICE_CENTS) {
    return { ok: false, reason: 'price outside allowed range' }
  }
  return screenText(required.map((k) => String(idea[k])).join(' '))
}

export const actionAllowed = (action: string) => ALLOWED_ACTIONS.has(action)
