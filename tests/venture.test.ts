import { describe, it, expect, beforeEach, vi } from 'vitest'
import { randomUUID } from 'crypto'
import { VentureEngine, configFromEnv, EngineConfig } from '../lib/venture/engine'
import { Store, Filters, Row } from '../lib/venture/store'
import { LLM, LLMUnavailable } from '../lib/venture/llm'
import { Channel, Bluesky, Mastodon, XTwitter, DevTo, DISCLOSURE, indexNow } from '../lib/venture/channels'

const TABLES = ['divisions', 'division_agents', 'activity_log', 'products', 'articles', 'ledger', 'distributions']

class FakeStore implements Store {
  t: Record<string, Row[]> = Object.fromEntries(TABLES.map((k) => [k, []]))

  private match(row: Row, f: Filters) {
    return Object.entries(f).every(([k, spec]) => {
      const i = spec.indexOf('.')
      const op = spec.slice(0, i), val = spec.slice(i + 1)
      const cur = row[k]
      if (op === 'eq') return String(cur) === val
      if (op === 'neq') return String(cur) !== val
      if (op === 'gte') return cur != null && cur >= val
      return false
    })
  }

  async select(table: string, f: Filters = {}, opts: { limit?: number } = {}) {
    if (table === 'division_pnl') {
      const rows = this.t.divisions.map((d) => ({ division_id: d.id, ...this.sums(d.id) }))
      return rows.filter((r) => this.match(r, f))
    }
    const rows = this.t[table].filter((r) => this.match(r, f))
    return opts.limit ? rows.slice(0, opts.limit) : rows
  }

  private sums(id: string) {
    const led = this.t.ledger.filter((l) => l.division_id === id)
    const s = (k: string) => led.filter((l) => l.kind === k).reduce((a, l) => a + l.amount_cents, 0)
    return { revenue_cents: s('revenue'), refund_cents: s('refund'), cost_cents: s('cost'),
      profit_cents: s('revenue') - s('refund') - s('cost') }
  }

  async insert(table: string, row: Row) {
    const now = new Date().toISOString()
    const full = { id: randomUUID(), status: table === 'divisions' ? 'active' : table === 'division_agents' ? 'idle' : 'published',
      tasks_completed: 0, cycle: 1, baseline_profit_cents: 0, started_at: now, created_at: now, ...row }
    this.t[table].push(full)
    return full
  }

  async patch(table: string, m: Filters, values: Row) {
    this.t[table].filter((r) => this.match(r, m)).forEach((r) => Object.assign(r, values))
  }

  async pnl(id: string) { return this.sums(id) }
}

const IDEA = { name: 'Cafe Price Check', thesis: 'Small cafes need quick price benchmarks',
  audience: 'independent cafe owners', product_title: 'Cafe pricing worksheet', price_cents: 900, score: 8 }

const stubLlm: LLM = async (system) => {
  if (system.includes('venture analyst')) {
    return { costCents: 4, data: { ideas: [IDEA, { ...IDEA, name: 'Casino Tips', thesis: 'online casino tips', score: 9 }] } }
  }
  if (system.includes('strict reviewer')) return { costCents: 1, data: { approved: true, issues: [] } }
  if (system.includes('single digital product')) {
    return { costCents: 2, data: { title: 'Cafe pricing worksheet', description: 'A worksheet.', price_cents: 900,
      deliverable: '# Worksheet\n1. List costs' } }
  }
  return { costCents: 2, data: { title: 'How to price a flat white', body: 'Body text' } }
}

class FakeChannel implements Channel {
  name = 'fake'
  posts: string[][] = []
  constructor(private fail = false) {}
  enabled = () => true
  limit = () => 300
  preview = (title: string, url: string) => `${title}\n${url}\n${DISCLOSURE}`
  async post(_f: typeof fetch, title: string, url: string) {
    if (this.fail) throw new Error('boom')
    this.posts.push([title, url])
    return `ref${this.posts.length}`
  }
}

function make(over: Partial<EngineConfig> = {}, channels: Channel[] = [], llm: LLM = stubLlm, now?: () => Date) {
  const store = new FakeStore()
  const config = { ...configFromEnv({}), maxDivisions: 1, siteUrl: '', ...over }
  return { store, engine: new VentureEngine({ store, llm, channels, config, now }) }
}

beforeEach(() => { vi.unstubAllEnvs() })

describe('venture engine', () => {
  it('launches, builds, publishes, and rejects forbidden ideas', async () => {
    const { store, engine } = make()
    await engine.tick()
    expect(store.t.divisions.map((d) => d.name)).toEqual(['Cafe Price Check'])
    expect(store.t.products).toHaveLength(1)
    await engine.tick()
    expect(store.t.articles).toHaveLength(1)
    expect(new Set(store.t.division_agents.map((a) => a.role))).toEqual(new Set(['researcher', 'builder', 'marketer']))
    expect(store.t.ledger.every((l) => l.kind === 'cost')).toBe(true)
  })

  it('deletes a division with no profit at the deadline', async () => {
    const { store, engine } = make({ maxDivisions: 1 })
    await engine.tick()
    const d = store.t.divisions[0]
    d.deadline = new Date(Date.now() - 60_000).toISOString()
    await engine.tick()
    expect(d.status).toBe('deleted')
    expect(d.end_reason).toContain('no profit')
    expect(store.t.division_agents.filter((a) => a.division_id === d.id).every((a) => a.status === 'retired')).toBe(true)
    expect(store.t.products.filter((p) => p.division_id === d.id).every((p) => p.status === 'archived')).toBe(true)
    expect(store.t.divisions.filter((x) => x.status === 'active')).toHaveLength(1) // replacement launched
  })

  it('renews a profitable division and spawns support', async () => {
    const { store, engine } = make()
    await engine.tick()
    await engine.tick()
    const d = store.t.divisions[0]
    await store.insert('ledger', { division_id: d.id, kind: 'revenue', amount_cents: 5000, ref: 'r1' })
    await engine.tick()
    expect(store.t.division_agents.map((a) => a.role)).toContain('support')
    d.deadline = new Date(Date.now() - 60_000).toISOString()
    await engine.tick()
    expect(d.status).toBe('active')
    expect(d.cycle).toBe(2)
    expect(d.baseline_profit_cents).toBeGreaterThan(0)
  })

  it('deletes an unprofitable division that exhausts its budget', async () => {
    const { store, engine } = make()
    await engine.tick()
    const d = store.t.divisions[0]
    await engine.cost(d, d.budget_cents, 'spent')
    await engine.tick()
    expect(d.status).toBe('deleted')
    expect(d.end_reason).toContain('budget')
  })

  it('launches nothing without an LLM key', async () => {
    const noKey: LLM = async () => { throw new LLMUnavailable('none') }
    const { store, engine } = make({}, [], noKey)
    await engine.tick()
    expect(store.t.divisions).toEqual([])
  })

  it('stops launching after the lifetime loss cap', async () => {
    const { store, engine } = make({ lifetimeLossCapCents: 5 })
    const d = await store.insert('divisions', { name: 'old', status: 'deleted', budget_cents: 100, deadline: '2020-01-01' })
    await engine.cost(d, 10, 'loss')
    await engine.tick()
    expect(store.t.divisions).toHaveLength(1)
  })
})

describe('distribution', () => {
  it('posts with daily cap and isolates channel failures', async () => {
    const ok = new FakeChannel()
    const bad = new FakeChannel(true)
    bad.name = 'bad'
    const { store, engine } = make({ siteUrl: 'https://site.example', dailyPostCap: 2 }, [ok, bad])
    for (let i = 0; i < 4; i++) await engine.tick()
    expect(ok.posts).toHaveLength(2) // product + first article, then capped
    expect(ok.posts.every(([, url]) => url.startsWith('https://site.example/'))).toBe(true)
    const failed = store.t.distributions.filter((r) => r.status === 'failed')
    expect(failed.length).toBeGreaterThan(0)
    expect(failed.every((r) => r.channel === 'bad')).toBe(true)
  })

  it('does not post without SITE_URL', async () => {
    const ch = new FakeChannel()
    const { engine } = make({ siteUrl: '' }, [ch])
    await engine.tick()
    expect(ch.posts).toEqual([])
  })

  it('dry run sends nothing and logs the exact text', async () => {
    const ch = new FakeChannel()
    const { store, engine } = make({ siteUrl: 'https://site.example', dryRun: true }, [ch])
    await engine.tick()
    await engine.tick()
    expect(ch.posts).toEqual([])
    expect(store.t.distributions).toEqual([])
    const previews = store.t.activity_log.filter((a) => a.kind === 'dry_run').map((a) => a.summary)
    expect(previews[0]).toContain('would post to fake')
    expect(previews[0]).toContain('https://site.example/p/')
    expect(previews[0]).toContain(DISCLOSURE)
  })
})

describe('channel adapters', () => {
  const URL = 'https://site.example/blog/how-to-price'

  it('bluesky posts a link facet with the right byte range and disclosure', async () => {
    vi.stubEnv('BLUESKY_HANDLE', 'bot.bsky.social')
    vi.stubEnv('BLUESKY_APP_PASSWORD', 'pw')
    let body: any
    const f = (async (u: string, init: any) => {
      if (u.endsWith('createSession')) return new Response(JSON.stringify({ accessJwt: 'jwt', did: 'did:plc:1' }))
      body = JSON.parse(init.body)
      return new Response(JSON.stringify({ uri: 'at://did:plc:1/app.bsky.feed.post/1' }))
    }) as unknown as typeof fetch
    const ref = await new Bluesky().post(f, 'Pricing a flat white — café edition', URL)
    const { text, facets } = body.record
    const { byteStart, byteEnd } = facets[0].index
    expect(ref.startsWith('at://')).toBe(true)
    expect(Buffer.from(text).subarray(byteStart, byteEnd).toString()).toBe(URL)
    expect(text).toContain(DISCLOSURE)
    expect(text.length).toBeLessThanOrEqual(300)
  })

  it('mastodon, x and devto post and respect limits', async () => {
    vi.stubEnv('MASTODON_BASE_URL', 'https://m.example')
    vi.stubEnv('MASTODON_ACCESS_TOKEN', 't')
    vi.stubEnv('X_ACCESS_TOKEN', 't')
    vi.stubEnv('DEVTO_API_KEY', 'k')
    const sent: Record<string, string> = {}
    const f = (async (u: string, init: any) => {
      const host = new globalThis.URL(u).host
      sent[host] = String(init.body)
      if (host === 'm.example') return new Response(JSON.stringify({ url: 'https://m.example/1' }))
      if (host === 'api.twitter.com') return new Response(JSON.stringify({ data: { id: '42' } }))
      return new Response(JSON.stringify({ url: 'https://dev.to/a' }))
    }) as unknown as typeof fetch
    const long = 'T'.repeat(600)
    expect(await new Mastodon().post(f, long, URL)).toBe('https://m.example/1')
    expect(await new XTwitter().post(f, long, URL)).toBe('42')
    expect(JSON.parse(sent['api.twitter.com']).text.length - URL.length + 23).toBeLessThanOrEqual(280)
    expect(await new DevTo().post(f, 'Title', URL, 'body')).toBe('https://dev.to/a')
    expect(sent['dev.to']).toContain('canonical_url')
    expect(sent['dev.to']).toContain('written by AI')
    await expect(new DevTo().post(f, 'Title', URL)).rejects.toThrow('only carries articles')
    expect(new Bluesky().preview(long, URL).length).toBeLessThanOrEqual(300)
  })

  it('indexnow sends host, key and keyLocation', async () => {
    vi.stubEnv('SITE_URL', 'https://site.example')
    vi.stubEnv('INDEXNOW_KEY', 'abc12345')
    let body: any
    const f = (async (_u: string, init: any) => { body = JSON.parse(init.body); return new Response('') }) as unknown as typeof fetch
    await indexNow.ping(f, URL)
    expect(body.host).toBe('site.example')
    expect(body.keyLocation).toBe('https://site.example/indexnow-key')
  })
})
