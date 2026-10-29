// Distribution channels. Each is enabled only when its credentials are in the environment.
// Rules for every channel (enforced by the engine): original posts only (no replies, DMs, follows or
// mentions), every post discloses it is AI-written, and a per-division daily cap per channel.

export const DISCLOSURE = '(AI-written)'

type Fetch = typeof fetch

export interface Channel {
  name: string
  enabled(): boolean
  limit(url: string): number
  preview(title: string, url: string, body?: string): string
  post(f: Fetch, title: string, url: string, body?: string): Promise<string>
}

export function compose(title: string, url: string, maxLen: number): string {
  const tail = `\n${url}\n${DISCLOSURE}`
  const room = maxLen - tail.length
  const head = title.length <= room ? title : title.slice(0, room - 1).trimEnd() + '…'
  return head + tail
}

async function ok(res: Response) {
  if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`)
  return res.json()
}

abstract class Base implements Channel {
  abstract name: string
  abstract enabled(): boolean
  abstract post(f: Fetch, title: string, url: string, body?: string): Promise<string>
  limit(_url: string): number {
    return 300
  }
  preview(title: string, url: string, _body?: string) {
    return compose(title, url, this.limit(url))
  }
}

export class Bluesky extends Base {
  name = 'bluesky'
  enabled = () => !!(process.env.BLUESKY_HANDLE && process.env.BLUESKY_APP_PASSWORD)

  async post(f: Fetch, title: string, url: string) {
    const host = process.env.BLUESKY_HOST || 'https://bsky.social'
    const s = await ok(
      await f(`${host}/xrpc/com.atproto.server.createSession`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identifier: process.env.BLUESKY_HANDLE,
          password: process.env.BLUESKY_APP_PASSWORD
        })
      })
    )
    const text = compose(title, url, this.limit(url))
    const start = Buffer.byteLength(text.slice(0, text.indexOf(url)), 'utf8')
    const record = {
      $type: 'app.bsky.feed.post',
      text,
      langs: ['en'],
      createdAt: new Date().toISOString(),
      facets: [{
        index: { byteStart: start, byteEnd: start + Buffer.byteLength(url, 'utf8') },
        features: [{ $type: 'app.bsky.richtext.facet#link', uri: url }]
      }]
    }
    const r = await ok(
      await f(`${host}/xrpc/com.atproto.repo.createRecord`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${s.accessJwt}` },
        body: JSON.stringify({ repo: s.did, collection: 'app.bsky.feed.post', record })
      })
    )
    return r.uri as string
  }
}

export class Mastodon extends Base {
  name = 'mastodon'
  enabled = () => !!(process.env.MASTODON_BASE_URL && process.env.MASTODON_ACCESS_TOKEN)
  limit = () => 500

  async post(f: Fetch, title: string, url: string) {
    const r = await ok(
      await f(`${process.env.MASTODON_BASE_URL!.replace(/\/$/, '')}/api/v1/statuses`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${process.env.MASTODON_ACCESS_TOKEN}`,
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams({
          status: compose(title, url, this.limit()),
          visibility: 'public',
          language: 'en'
        })
      })
    )
    return r.url as string
  }
}

export class XTwitter extends Base {
  name = 'x'
  enabled = () => !!process.env.X_ACCESS_TOKEN
  // X counts every link as 23 characters
  limit = (url: string) => 280 - url.length + 23

  async post(f: Fetch, title: string, url: string) {
    const r = await ok(
      await f('https://api.twitter.com/2/tweets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.X_ACCESS_TOKEN}` },
        body: JSON.stringify({ text: compose(title, url, this.limit(url)) })
      })
    )
    return r.data.id as string
  }
}

// Cross-posts full articles with a canonical URL pointing back to our own page
export class DevTo extends Base {
  name = 'devto'
  enabled = () => !!process.env.DEVTO_API_KEY

  preview(title: string, url: string, body = '') {
    return `${title}\n${body.slice(0, 300)}...\n[canonical: ${url}]`
  }

  async post(f: Fetch, title: string, url: string, body?: string) {
    if (!body) throw new Error('devto only carries articles')
    const r = await ok(
      await f('https://dev.to/api/articles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'api-key': process.env.DEVTO_API_KEY! },
        body: JSON.stringify({
          article: {
            title,
            body_markdown: `${body}\n\n---\n*This article was written by AI. Original: ${url}*`,
            published: true,
            canonical_url: url
          }
        })
      })
    )
    return r.url as string
  }
}

// Tells Bing, Yandex and others about new URLs immediately. Needs SITE_URL and INDEXNOW_KEY.
export const indexNow = {
  enabled: () => !!(process.env.INDEXNOW_KEY && process.env.SITE_URL),
  async ping(f: Fetch, url: string) {
    const site = process.env.SITE_URL!.replace(/\/$/, '')
    const res = await f('https://api.indexnow.org/indexnow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        host: site.split('://').pop(),
        key: process.env.INDEXNOW_KEY,
        keyLocation: `${site}/indexnow-key`,
        urlList: [url]
      })
    })
    if (!res.ok) throw new Error(`IndexNow ${res.status}`)
  }
}

export const buildChannels = (): Channel[] =>
  [new Bluesky(), new Mastodon(), new XTwitter(), new DevTo()].filter((c) => c.enabled())
