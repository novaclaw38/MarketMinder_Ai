# MarketMinder AI - Vercel + Supabase Deployment

## Quick Deploy

```bash
npm install
vercel
```

## Environment Variables (in Vercel Dashboard)

### Required
- `NEXT_PUBLIC_SUPABASE_URL` - Your Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Public anon key
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key (for server-side operations)

### Optional
- `GROQ_API_KEY` - LLM for analysis and the venture engine (optional `GROQ_MODEL`, default `llama-3.3-70b-versatile`). `OPENAI_API_KEY` is used only if no Groq key is set.
- `STRIPE_SECRET_KEY` - For billing
- `STRIPE_WEBHOOK_SECRET` - Signing secret for the webhook at `/api/billing/webhook` (events: `checkout.session.completed`, `customer.subscription.*`, `invoice.paid`, `charge.refunded`)
- `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PROFESSIONAL`, `STRIPE_PRICE_ENTERPRISE` - Stripe recurring price IDs
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` is also used by the login page
- `CRON_SECRET` - Bearer secret for cron and machine callers (also required for `POST /api/agents`)

---

## Supabase Setup

### 1. Create Project
Go to https://supabase.com and create a new project.

### 2. Run Schema SQL

```sql
-- Health check table
CREATE TABLE health_check (
  id INTEGER PRIMARY KEY DEFAULT 1,
  health_score FLOAT DEFAULT 100.0,
  cash_runway_days INTEGER DEFAULT 90
);

-- Agents status
CREATE TABLE agent_status (
  agent_name TEXT PRIMARY KEY,
  status TEXT DEFAULT 'idle',
  last_updated TIMESTAMP DEFAULT NOW(),
  tasks_completed INTEGER DEFAULT 0,
  error_count INTEGER DEFAULT 0,
  data JSONB
);

-- Metrics tracking
CREATE TABLE metrics (
  id INTEGER PRIMARY KEY DEFAULT 1,
  metric_name TEXT UNIQUE,
  value FLOAT,
  target FLOAT,
  last_updated TIMESTAMP DEFAULT NOW()
);

-- Analysis requests from users
CREATE TABLE analysis_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  query TEXT,
  segment TEXT,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  result JSONB
);
```

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 Vercel Edge                     │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │   Dashboard │  │   API       │  │   Cron    │ │
│  │   (Next.js) │  │   Routes    │  │  Jobs    │ │
│  └─────────────┘  └─────────────┘  └──────────┘ │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│              Supabase Database                 │
└─────────────────────────────────────────────────┘
```

---

## Deploy Instructions

1. **Push to GitHub**:
```bash
git add .
git commit -m "Vercel + Supabase deployment ready"
git push origin main
```

2. **Import to Vercel**:
   - Go to https://vercel.com/new
   - Import from GitHub: `novaclaw38/MarketMinder_Ai`
   - Configure environment variables

3. **Set Environment Variables in Vercel**:
```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Cost

- **Vercel**: Free tier (100GB bandwidth, 1000 hours)
- **Supabase**: Free tier (500MB database, 1GB storage)
- **Estimated**: $0-5/month for low usage

## Files Structure

```
marketminder-ai/
├── app/
│   ├── api/
│   │   ├── analyze/route.ts      # Market analysis endpoint
│   │   ├── agents/route.ts       # Agent status & control
│   │   ├── metrics/route.ts      # Metrics dashboard
│   │   └── cron/orchestrate/route.ts  # Agent scheduler
│   ├── dashboard/page.tsx        # Mission Control UI
│   └── layout.tsx
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql
├── vercel.json
├── package.json
├── tailwind.config.js
└── VERCEL_DEPLOY.md
```
---

## Venture engine (runs on Vercel)

The engine runs inside Vercel: `/api/cron/venture` launches divisions when there is capacity, evaluates deadlines, and gives every active division one step of work.

**Scheduling.** Vercel Hobby allows only daily crons, and a more frequent schedule makes the deploy fail ("Hobby accounts are limited to daily cron jobs"). So `vercel.json` has daily crons as a floor, and `.github/workflows/tick.yml` calls both endpoints every 10 minutes from GitHub Actions. Add two repository secrets (Settings -> Secrets and variables -> Actions): `APP_URL` (your production URL, no trailing slash) and `CRON_SECRET` (same value as in Vercel). GitHub's scheduler can delay runs by several minutes, which is fine here. On Vercel Pro you can instead set `*/10 * * * *` in `vercel.json` and delete the workflow. Scheduled workflows only run from the default branch, and Vercel crons only run on production deployments, so merge to your production branch first.

Requirements: `CRON_SECRET` set in Vercel, and `GROQ_API_KEY` (optional `GROQ_MODEL`, default `llama-3.3-70b-versatile`).

Check it by hand: `curl -H "Authorization: Bearer $CRON_SECRET" https://<your-app>/api/cron/venture` returns `{"ok":true,"dry_run":...,"launched":N,"deleted":N}`.

Tuning (all optional env vars): `MAX_ACTIVE_DIVISIONS` (3), `DIVISION_BUDGET_CENTS` (2000), `GLOBAL_BUDGET_CENTS` (6000), `LIFETIME_LOSS_CAP_CENTS` (10000), `WINDOW_DAYS` (7), `MAX_AGENTS_PER_DIVISION` (8), `DEFAULT_CURRENCY` (usd).

## Distribution channels

Set these in Vercel. A channel with no credentials is simply off.

| Variable(s) | Channel |
|---|---|
| `SITE_URL` (e.g. `https://your-app.vercel.app`) | **Required** for any distribution; used to build links and the sitemap |
| `INDEXNOW_KEY` (any 8-128 char hex/alnum string) | Instant indexing ping to Bing/Yandex; key is served at `/indexnow-key` |
| `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | Bluesky posts (use an app password, not your login password) |
| `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN` | Mastodon posts (token needs `write:statuses`) |
| `X_ACCESS_TOKEN` | X posts (OAuth 2.0 user token with `tweet.write`; tokens expire, so refresh as needed) |
| `DEVTO_API_KEY` | Full-article cross-posts to DEV with a canonical URL back to your blog |

Limits applied to every channel: original posts only (no replies, DMs, follows or mentions), an "(AI-written)" disclosure on each post, and `DAILY_POST_CAP_PER_CHANNEL` (default 3) per division. Run each account as a clearly labelled bot or automated account, as each platform's rules require.

### Dry run

Set `DRY_RUN=true` in Vercel to run everything (research, products, articles, budgets, deadlines) without sending anything to Bluesky, Mastodon, X, DEV.to or IndexNow. Each post that would have gone out is written to the division's activity feed as `DRY RUN, would post to <channel>: <exact text>`. Remove `DRY_RUN` to go live. Dry run does not stop the storefront, which is always public, and it still uses your Groq budget.
