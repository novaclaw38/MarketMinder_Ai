// Venture engine: researches business ideas, launches them as divisions with their own agents,
// budget and P&L, and deletes any division that has not made a profit within its window.
//
// Autonomy model: no human approval is requested at runtime. Safety comes from the hard limits in
// policy.ts and from the budget caps enforced here.

import { randomUUID } from 'crypto'
import * as policy from './policy'
import { LLM, LLMUnavailable } from './llm'
import { Channel, indexNow } from './channels'
import { Row, Store } from './store'

const HONESTY_RULES =
  'Rules you must follow: never invent statistics, quotes, testimonials, customer names or sources; ' +
  'if you are not sure of a fact, leave it out or say it is an estimate. Say plainly that the content ' +
  'is AI-generated. Do not give financial, legal or medical advice. Do not promise results.'

const DAY_MS = 86_400_000
const HOUR_MS = 3_600_000

export interface EngineConfig {
  maxDivisions: number
  divisionBudgetCents: number
  globalBudgetCents: number
  lifetimeLossCapCents: number
  windowMs: number
  maxAgents: number
  currency: string
  siteUrl: string
  dailyPostCap: number
  dryRun: boolean
}

export function configFromEnv(env: Record<string, string | undefined> = process.env): EngineConfig {
  const n = (k: string, d: number) => Number(env[k] ?? d)
  return {
    maxDivisions: n('MAX_ACTIVE_DIVISIONS', 3),
    divisionBudgetCents: n('DIVISION_BUDGET_CENTS', 2000),
    globalBudgetCents: n('GLOBAL_BUDGET_CENTS', 6000),
    lifetimeLossCapCents: n('LIFETIME_LOSS_CAP_CENTS', 10000),
    windowMs: n('WINDOW_DAYS', 7) * DAY_MS,
    maxAgents: n('MAX_AGENTS_PER_DIVISION', 8),
    currency: env.DEFAULT_CURRENCY ?? 'usd',
    siteUrl: (env.SITE_URL ?? '').replace(/\/$/, ''),
    dailyPostCap: n('DAILY_POST_CAP_PER_CHANNEL', 3),
    dryRun: ['1', 'true', 'yes'].includes((env.DRY_RUN ?? '').toLowerCase())
  }
}

export function slugify(text: string) {
  const base = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40)
  return `${base}-${randomUUID().slice(0, 6)}`
}

export interface Deps {
  store: Store
  llm: LLM
  channels: Channel[]
  config: EngineConfig
  fetch?: typeof fetch
  now?: () => Date
}

export class VentureEngine {
  private store: Store
  private llm: LLM
  private channels: Channel[]
  private cfg: EngineConfig
  private f: typeof fetch
  private now: () => Date

  constructor(d: Deps) {
    this.store = d.store
    this.llm = d.llm
    this.channels = d.channels
    this.cfg = d.config
    this.f = d.fetch ?? fetch
    this.now = d.now ?? (() => new Date())
  }

  // ---- main loop -----------------------------------------------------------------------------

  async tick(): Promise<{ launched: number; deleted: number }> {
    const before = await this.active()
    for (const d of before) await this.evaluate(d)
    const afterEval = await this.active()
    const deleted = before.length - afterEval.length

    const launched = await this.launchIfCapacity()

    // Divisions work in parallel so one slow LLM call doesn't starve the others
    await Promise.all(
      (await this.active()).map(async (d) => {
        try {
          await this.runAgents(d)
        } catch (e: any) {
          const msg = e instanceof LLMUnavailable ? 'GROQ_API_KEY missing; division cannot work' : `step failed: ${e.message}`
          await this.log(d, 'system', e instanceof LLMUnavailable ? 'blocked' : 'error', msg)
        }
      })
    )
    return { launched, deleted }
  }

  private active() {
    return this.store.select('divisions', { status: 'eq.active' }, { order: 'started_at.asc' })
  }

  // ---- the deadline: profit or be deleted -----------------------------------------------------

  async evaluate(d: Row) {
    const pnl = await this.store.pnl(d.id)
    const cycleProfit = pnl.profit_cents - d.baseline_profit_cents

    if (pnl.cost_cents >= d.budget_cents && cycleProfit <= 0) {
      await this.windDown(d, 'budget exhausted without profit')
    } else if (this.now() >= new Date(d.deadline)) {
      if (cycleProfit > 0) {
        await this.store.patch('divisions', { id: `eq.${d.id}` }, {
          cycle: d.cycle + 1,
          baseline_profit_cents: pnl.profit_cents,
          deadline: new Date(this.now().getTime() + this.cfg.windowMs).toISOString()
        })
        await this.log(d, 'orchestrator', 'renewed', `Profit ${cycleProfit}c this cycle; renewed for another window`)
      } else {
        await this.windDown(d, 'no profit within the window')
      }
    }
  }

  // Delete a division: stop selling, retire agents, keep the ledger for accounting
  async windDown(d: Row, reason: string) {
    const by = { division_id: `eq.${d.id}` }
    await this.store.patch('divisions', { id: `eq.${d.id}` }, {
      status: 'deleted', ended_at: this.now().toISOString(), end_reason: reason
    })
    await this.store.patch('division_agents', by, { status: 'retired' })
    await this.store.patch('products', by, { status: 'archived' })
    await this.store.patch('articles', by, { status: 'archived' })
    await this.log(d, 'orchestrator', 'deleted', `Division deleted: ${reason}`)
  }

  // ---- research and launch ---------------------------------------------------------------------

  private async launchIfCapacity(): Promise<number> {
    const active = await this.active()
    const capacity = this.cfg.maxDivisions - active.length
    const committed = active.reduce((s, d) => s + d.budget_cents, 0)
    if (capacity <= 0 || committed + this.cfg.divisionBudgetCents > this.cfg.globalBudgetCents) return 0

    const all = await this.store.select('division_pnl')
    if (all.reduce((s, p) => s + p.profit_cents, 0) <= -this.cfg.lifetimeLossCapCents) return 0

    let research
    try {
      research = await this.research(await this.lessons())
    } catch (e) {
      if (e instanceof LLMUnavailable) return 0
      throw e
    }

    const slots = Math.min(capacity, Math.floor((this.cfg.globalBudgetCents - committed) / this.cfg.divisionBudgetCents))
    const launched: Row[] = []
    for (const idea of [...research.ideas].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))) {
      if (launched.length >= slots) break
      if (!policy.screenIdea(idea).ok) continue
      launched.push(await this.spawnDivision(idea))
    }
    for (const d of launched) {
      await this.cost(d, Math.floor(research.costCents / launched.length), 'Market research')
    }
    return launched.length
  }

  private async lessons() {
    const dead = await this.store.select('divisions', { status: 'eq.deleted' }, { limit: 10, columns: 'name,thesis,end_reason' })
    return dead.map((d) => `${d.name}: ${d.thesis} (deleted: ${d.end_reason})`)
  }

  private async research(lessons: string[]) {
    const system =
      'You are a venture analyst picking businesses that can earn their first profit within 7 days ' +
      'with almost no capital, run entirely by software. Each must sell a digital product that can be ' +
      'generated and delivered instantly and automatically, to a clearly defined audience, and be ' +
      'discoverable through search-indexed web pages. Prefer a narrow niche with an urgent, specific need ' +
      `and a low price (USD 5-49). ${HONESTY_RULES} Reply as JSON: ` +
      '{"ideas":[{"name":str,"thesis":str,"audience":str,"product_title":str,"price_cents":int,' +
      '"score":number 1-10,"why_it_could_work_this_week":str}]}. Give 5 distinct ideas.'
    const { data, costCents } = await this.llm(system, `Failed before (avoid repeating): ${lessons.join('; ') || 'nothing yet'}`)
    return { ideas: (data.ideas ?? []) as policy.Idea[], costCents }
  }

  private async spawnDivision(idea: policy.Idea) {
    const d = await this.store.insert('divisions', {
      name: idea.name,
      slug: slugify(idea.name),
      thesis: idea.thesis,
      audience: idea.audience,
      budget_cents: this.cfg.divisionBudgetCents,
      score: idea.score ?? 0,
      deadline: new Date(this.now().getTime() + this.cfg.windowMs).toISOString()
    })
    for (const role of ['researcher', 'builder', 'marketer']) await this.spawnAgent(d, role, 'initial team')
    await this.log(d, 'orchestrator', 'launched', `Launched '${idea.name}' for ${idea.audience}; deadline ${d.deadline}`, { idea })
    return d
  }

  // ---- agents -----------------------------------------------------------------------------------

  async spawnAgent(d: Row, role: string, reason: string) {
    const agents = await this.store.select('division_agents', { division_id: `eq.${d.id}`, status: 'neq.retired' })
    if (agents.length >= this.cfg.maxAgents) return false
    await this.store.insert('division_agents', { division_id: d.id, role, spawned_reason: reason })
    await this.log(d, 'orchestrator', 'agent_spawned', `Spawned ${role}: ${reason}`)
    return true
  }

  private async touchAgent(d: Row, role: string) {
    const [a] = await this.store.select('division_agents',
      { division_id: `eq.${d.id}`, role: `eq.${role}`, status: 'neq.retired' }, { limit: 1 })
    if (a) {
      await this.store.patch('division_agents', { id: `eq.${a.id}` }, {
        tasks_completed: a.tasks_completed + 1, last_active_at: this.now().toISOString()
      })
    }
  }

  private async runAgents(d: Row) {
    const pnl = await this.store.pnl(d.id)
    if (pnl.cost_cents >= d.budget_cents) return // out of budget: wait for revenue or the deadline

    const products = await this.store.select('products', { division_id: `eq.${d.id}`, status: 'eq.published' })
    if (!products.length) {
      await this.buildProduct(d)
      return
    }

    // Scale rules: agents are added only when they have evidence to act on
    if (pnl.revenue_cents > 0) {
      await this.spawnAgent(d, 'support', 'first revenue received')
      if (Math.floor(pnl.profit_cents / 2000) >= 1) await this.spawnAgent(d, 'marketer', 'profit funds more content')
    } else if (this.now().getTime() - new Date(d.started_at).getTime() >= 2 * DAY_MS && products.length < 2) {
      await this.spawnAgent(d, 'experimenter', 'no revenue after 2 days: test a new offer')
      await this.buildProduct(d, products[0])
      return
    }

    const since = new Date(this.now().getTime() - 12 * HOUR_MS).toISOString()
    const recent = await this.store.select('articles', { division_id: `eq.${d.id}`, created_at: `gte.${since}` })
    if (recent.length < 2) await this.publishArticle(d, products[0])
  }

  // ---- work: build, review, publish ----------------------------------------------------------------

  private async buildProduct(d: Row, variantOf?: Row) {
    let context = `Business: ${d.name}. Thesis: ${d.thesis}. Audience: ${d.audience}.`
    if (variantOf) {
      context += ` The existing offer '${variantOf.title}' at ${variantOf.price_cents}c has not sold. ` +
        'Create a clearly different offer: new angle or format, different price point.'
    }
    const system =
      `You create a single digital product that is delivered instantly as text. ${HONESTY_RULES} ` +
      'The deliverable must be genuinely useful and specific (a checklist, template pack, structured guide ' +
      'or worked analysis), 500-900 words, markdown. Reply as JSON: ' +
      '{"title":str,"description":str (max 60 words, honest, no hype),"price_cents":int,"deliverable":str}.'
    const { data, costCents } = await this.llm(system, context)
    await this.cost(d, costCents, 'Product drafting')

    const screen = policy.screenText(`${data.title ?? ''} ${data.description ?? ''} ${data.deliverable ?? ''}`)
    const price = data.price_cents
    const priceOk = Number.isInteger(price) && price >= policy.MIN_PRICE_CENTS && price <= policy.MAX_PRICE_CENTS
    if (!screen.ok || !priceOk) {
      await this.log(d, 'builder', 'rejected', `Product failed policy screen: ${screen.ok ? 'bad price' : screen.reason}`)
      return
    }

    const review = await this.llm(
      'You are a strict reviewer. Reject content that contains invented statistics, fake sources or quotes, ' +
        'unprovable claims, financial/legal/medical advice, or that is generic filler. Reply as JSON: ' +
        '{"approved":bool,"issues":[str]}.',
      `${data.deliverable}\n\nDescription: ${data.description}`
    )
    await this.cost(d, review.costCents, 'Product review')
    if (!review.data.approved) {
      await this.log(d, 'reviewer', 'rejected', 'Product rejected by reviewer', { issues: review.data.issues ?? [] })
      return
    }

    const product = await this.store.insert('products', {
      division_id: d.id, slug: slugify(data.title), title: data.title, description: data.description,
      price_cents: price, currency: this.cfg.currency, deliverable: data.deliverable
    })
    await this.touchAgent(d, 'builder')
    await this.log(d, 'builder', 'product_published', `Published '${product.title}' at ${price}c: /p/${product.slug}`)
    await this.distribute(d, 'product', product.title, `/p/${product.slug}`)
  }

  private async publishArticle(d: Row, product: Row) {
    const system =
      'You write one helpful, search-friendly article (400-700 words, markdown) for the audience below that ' +
      'teaches something real and naturally leads to the product, which you may mention once at the end ' +
      `without hype. ${HONESTY_RULES} Reply as JSON: {"title":str,"body":str}.`
    const { data, costCents } = await this.llm(system,
      `Audience: ${d.audience}. Product: ${product.title} - ${product.description}. ` +
      'Pick a specific question this audience would search for.')
    await this.cost(d, costCents, 'Article drafting')
    const screen = policy.screenText(`${data.title ?? ''} ${data.body ?? ''}`)
    if (!screen.ok) {
      await this.log(d, 'marketer', 'rejected', `Article failed policy screen: ${screen.reason}`)
      return
    }
    const article = await this.store.insert('articles', {
      division_id: d.id, product_id: product.id, slug: slugify(data.title), title: data.title, body: data.body
    })
    await this.touchAgent(d, 'marketer')
    await this.log(d, 'marketer', 'article_published', `Published article: /blog/${article.slug}`)
    await this.distribute(d, 'article', article.title, `/blog/${article.slug}`, article.body)
  }

  // ---- distribution -----------------------------------------------------------------------------------

  // Announce new content on every enabled channel, within per-channel daily caps
  private async distribute(d: Row, kind: 'article' | 'product', title: string, path: string, body?: string) {
    if (!this.cfg.siteUrl || !policy.actionAllowed('distribute_post')) return
    const url = `${this.cfg.siteUrl}${path}`
    const targets = this.channels.filter((c) => !(kind === 'product' && c.name === 'devto'))

    if (this.cfg.dryRun) {
      for (const c of targets) {
        await this.log(d, 'marketer', 'dry_run', `DRY RUN, would post to ${c.name}: ${c.preview(title, url, body)}`)
      }
      if (indexNow.enabled()) await this.log(d, 'marketer', 'dry_run', `DRY RUN, would submit ${path} to IndexNow`)
      return
    }

    if (indexNow.enabled()) {
      try {
        await indexNow.ping(this.f, url)
        await this.log(d, 'marketer', 'indexed', `Submitted ${path} to IndexNow`)
      } catch (e: any) {
        console.warn('IndexNow failed:', e.message)
      }
    }

    const since = new Date(this.now().getTime() - 24 * HOUR_MS).toISOString()
    for (const c of targets) {
      const recent = await this.store.select('distributions',
        { division_id: `eq.${d.id}`, channel: `eq.${c.name}`, status: 'eq.posted', created_at: `gte.${since}` })
      if (recent.length >= this.cfg.dailyPostCap) continue
      const row = { division_id: d.id, channel: c.name, kind, target_url: url }
      try {
        const ref = await c.post(this.f, title, url, body)
        await this.store.insert('distributions', { ...row, status: 'posted', external_ref: ref })
        await this.log(d, 'marketer', 'distributed', `Posted to ${c.name}: ${ref}`)
      } catch (e: any) {
        // One failure must not trigger retries or a posting storm
        await this.store.insert('distributions', { ...row, status: 'failed', error: String(e.message).slice(0, 300) })
        await this.log(d, 'marketer', 'distribution_failed', `${c.name} failed: ${e.message}`)
      }
    }
  }

  // ---- bookkeeping -------------------------------------------------------------------------------------

  async cost(d: Row, cents: number, description: string) {
    await this.store.insert('ledger', {
      division_id: d.id, kind: 'cost', amount_cents: cents, description, ref: `cost:${randomUUID()}`
    })
  }

  async log(d: Row, role: string, kind: string, summary: string, payload?: Row) {
    await this.store.insert('activity_log', { division_id: d.id, agent_role: role, kind, summary, payload })
  }
}
