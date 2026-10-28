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
  cash_runway_days INTEGER DEFAULT 90,
  last_updated TIMESTAMP DEFAULT NOW()
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

-- Analysis requests
CREATE TABLE analysis_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  query TEXT,
  segment TEXT,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  result JSONB
);

-- Customers (for billing)
CREATE TABLE customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE,
  stripe_customer_id TEXT,
  subscription_status TEXT DEFAULT 'active',
  mrr FLOAT DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 3. Insert Initial Data

```sql
-- Initial health check
INSERT INTO health_check (health_score, cash_runway_days) 
VALUES (100, 90);

-- Agent status
INSERT INTO agent_status (agent_name, status, tasks_completed) VALUES
('market_scout', 'idle', 0),
('product_builder', 'idle', 0),
('finance_controller', 'idle', 0),
('marketing_engine', 'idle', 0),
('customer_success', 'idle', 0),
('sales_closer', 'idle', 0);

-- Metrics
INSERT INTO metrics (metric_name, value, target) VALUES
('mrr', 0, 5000),
('churn_rate', 0, 0.05),
('cac', 0, 250),
('ltv_cac', 0, 3);
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
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │   health_   │  │ agent_      │  │ metrics  │ │
│  │   check     │  │ status      │  │   table  │ │
│  └─────────────┘  └─────────────┘  └──────────┘ │
└─────────────────────────────────────────────────┘
```

---

## Agent Integration

For each agent, create a Python script in `agents/` that:

1. Uses Supabase client to read/write data
2. Runs on Vercel Cron jobs or external triggers
3. Updates agent_status table

Example agent wrapper:

```python
import os
from supabase import create_client, Client

def run_market_scout():
    supabase: Client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"]
    )
    
    # Update agent status
    supabase.table("agent_status").update({
        "status": "processing",
        "tasks_completed": 1
    }).eq("agent_name", "market_scout").execute()
    
    # Your agent logic here
    
    # Update status on completion
    supabase.table("agent_status").update({
        "status": "idle"
    }).eq("agent_name", "market_scout").execute()
```

---

## Deploy Cron Jobs

Create `/api/cron/agents/route.ts` for scheduled agent runs:

```typescript
// Runs every 5 minutes
export const revalidate = 300

export async function GET() {
  // Trigger agent workflows
  // Use Supabase edge functions or external Python scripts
}
```

---

## Local Development

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# API endpoints:
# http://localhost:3000/api/health
# http://localhost:3000/api/metrics
# http://localhost:3000/api/agents
# http://localhost:3000/dashboard
```

---

## Monitoring

- Health Score: Check `/api/metrics` endpoint
- Agent status: Check `/api/agents` endpoint
- Logs: Vercel deployment logs

---

## Cost

- Vercel: Free tier (100GB bandwidth, 1000 hours)
- Supabase: Free tier (500MB database, 1GB storage)
- Estimated: $0-5/month for low usage