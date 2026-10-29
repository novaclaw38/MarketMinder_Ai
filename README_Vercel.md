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
- `OPENAI_API_KEY` - For advanced market analysis
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