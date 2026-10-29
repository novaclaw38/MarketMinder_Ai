-- Autonomous venture engine: divisions, their agents, products, content and P&L ledger

create table divisions (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  slug text unique not null,
  thesis text not null,
  audience text,
  status text default 'active' not null check (status in ('active', 'deleted')),
  cycle integer default 1 not null,
  budget_cents integer not null,
  baseline_profit_cents integer default 0 not null,
  score double precision default 0,
  started_at timestamp with time zone default now(),
  deadline timestamp with time zone not null,
  ended_at timestamp with time zone,
  end_reason text
);

create table division_agents (
  id uuid primary key default uuid_generate_v4(),
  division_id uuid not null references divisions(id) on delete cascade,
  role text not null,
  status text default 'idle' not null check (status in ('idle', 'working', 'retired')),
  tasks_completed integer default 0,
  spawned_reason text,
  created_at timestamp with time zone default now(),
  last_active_at timestamp with time zone
);

create table activity_log (
  id uuid primary key default uuid_generate_v4(),
  division_id uuid references divisions(id) on delete cascade,
  agent_role text,
  kind text not null,
  summary text not null,
  payload jsonb,
  created_at timestamp with time zone default now()
);
create index idx_activity_division on activity_log (division_id, created_at desc);

create table products (
  id uuid primary key default uuid_generate_v4(),
  division_id uuid not null references divisions(id) on delete cascade,
  slug text unique not null,
  title text not null,
  description text not null,
  price_cents integer not null check (price_cents >= 100),
  currency text default 'usd' not null,
  deliverable text not null,
  status text default 'published' not null check (status in ('published', 'archived')),
  created_at timestamp with time zone default now()
);

create table articles (
  id uuid primary key default uuid_generate_v4(),
  division_id uuid not null references divisions(id) on delete cascade,
  product_id uuid references products(id) on delete set null,
  slug text unique not null,
  title text not null,
  body text not null,
  status text default 'published' not null check (status in ('published', 'archived')),
  created_at timestamp with time zone default now()
);

-- Every revenue, cost and refund; ref makes webhook/engine writes idempotent
create table ledger (
  id uuid primary key default uuid_generate_v4(),
  division_id uuid not null references divisions(id) on delete cascade,
  kind text not null check (kind in ('revenue', 'cost', 'refund')),
  amount_cents integer not null check (amount_cents >= 0),
  description text,
  ref text unique,
  created_at timestamp with time zone default now()
);
create index idx_ledger_division on ledger (division_id, created_at desc);

create view division_pnl with (security_invoker = true) as
select
  d.id as division_id,
  coalesce(sum(l.amount_cents) filter (where l.kind = 'revenue'), 0)::integer as revenue_cents,
  coalesce(sum(l.amount_cents) filter (where l.kind = 'refund'), 0)::integer as refund_cents,
  coalesce(sum(l.amount_cents) filter (where l.kind = 'cost'), 0)::integer as cost_cents,
  (coalesce(sum(l.amount_cents) filter (where l.kind = 'revenue'), 0)
   - coalesce(sum(l.amount_cents) filter (where l.kind = 'refund'), 0)
   - coalesce(sum(l.amount_cents) filter (where l.kind = 'cost'), 0))::integer as profit_cents
from divisions d
left join ledger l on l.division_id = d.id
group by d.id;

alter table divisions enable row level security;
alter table division_agents enable row level security;
alter table activity_log enable row level security;
alter table products enable row level security;
alter table articles enable row level security;
alter table ledger enable row level security;

create policy "authenticated read divisions" on divisions for select to authenticated using (true);
create policy "authenticated read division_agents" on division_agents for select to authenticated using (true);
create policy "authenticated read activity_log" on activity_log for select to authenticated using (true);
create policy "authenticated read ledger" on ledger for select to authenticated using (true);
-- Storefront and blog are served by the API with the service key; products/articles need no client policy.
