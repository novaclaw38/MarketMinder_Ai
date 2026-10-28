-- Bootstrap MarketMinder AI database schema
-- Run this in Supabase SQL editor

-- Enable UUID generation
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- Health check table - single row with current health metrics
create table health_check (
  id integer primary key default 1,
  health_score double precision default 100.0,
  mrr double precision default 0,
  churn_rate double precision default 0,
  cash_runway_days integer default 90,
  cac double precision default 0,
  ltv_cac double precision default 0,
  last_updated timestamp with time zone default now()
);

-- Initialize health check row
insert into health_check (id, health_score, mrr, churn_rate, cash_runway_days, cac, ltv_cac)
values (1, 100.0, 0, 0, 90, 0, 0)
on conflict (id) do nothing;

-- Agent status tracking
create table agent_status (
  agent_name text primary key,
  status text default 'idle' not null check (status in ('idle', 'processing', 'error', 'offline', 'needs_attention')),
  last_updated timestamp with time zone default now(),
  tasks_completed integer default 0,
  error_count integer default 0,
  data jsonb,
  current_task_id uuid,
  queue_length integer default 0
);

-- Pre-populate agents
insert into agent_status (agent_name, status, tasks_completed, queue_length) values
('market_scout', 'idle', 0, 0),
('product_builder', 'idle', 0, 0),
('finance_controller', 'idle', 0, 0),
('marketing_engine', 'idle', 0, 0),
('customer_success', 'idle', 0, 0),
('sales_closer', 'idle', 0, 0)
on conflict (agent_name) do nothing;

-- Metrics tracking
create table metrics (
  id integer primary key default 1,
  metric_name text unique not null,
  value double precision,
  target double precision,
  last_updated timestamp with time zone default now()
);

insert into metrics (id, metric_name, value, target) values
(1, 'mrr', 0, 5000),
(2, 'churn_rate', 0, 0.05),
(3, 'cac', 0, 250),
(4, 'ltv_cac', 0, 3),
(5, 'tasks_per_hour', 0, 100)
on conflict (metric_name) do nothing;

-- Analysis requests from users
create table analysis_requests (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid,
  query text,
  segment text,
  scope text,
  status text default 'pending' not null check (status in ('pending', 'processing', 'completed', 'failed')),
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  completed_at timestamp with time zone,
  result jsonb,
  error_message text,
  tokens_used integer,
  cost_cents integer
);

-- Create indexes for performance
create index idx_analysis_requests_status on analysis_requests (status);
create index idx_analysis_requests_user on analysis_requests (user_id);
create index idx_analysis_requests_created on analysis_requests (created_at desc);

-- Customers and subscriptions
create table customers (
  id uuid primary key default uuid_generate_v4(),
  email text unique not null,
  stripe_customer_id text unique,
  subscription_status text default 'active' check (subscription_status in ('active', 'trialing', 'past_due', 'canceled', 'incomplete')),
  subscription_tier text default 'starter' check (subscription_tier in ('starter', 'professional', 'enterprise')),
  mrr double precision default 0,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  last_payment_at timestamp with time zone,
  current_period_end timestamp with time zone
);

-- Insert default customer row (for bootstrap)
insert into customers (id, email, subscription_status, subscription_tier)
values ('00000000-0000-0000-0000-000000000000', 'system@marketminder.ai', 'active', 'starter')
on conflict (id) do nothing;

-- Financial transactions
create table transactions (
  id uuid primary key default uuid_generate_v4(),
  customer_id uuid references customers(id),
  type text not null check (type in ('invoice', 'payment', 'refund', 'adjustment')),
  amount_cents integer not null,
  currency text default 'USD',
  status text default 'paid' check (status in ('paid', 'pending', 'failed', 'refunded')),
  stripe_invoice_id text,
  stripe_payment_intent_id text,
  description text,
  created_at timestamp with time zone default now()
);

-- Leads and pipeline
create table leads (
  id uuid primary key default uuid_generate_v4(),
  email text,
  company text,
  name text,
  score double precision default 0,
  stage text default 'prospect' check (stage in ('prospect', 'qualified', 'demo', 'proposal', 'closed_won', 'closed_lost')),
  source text,
  created_at timestamp with time zone default now(),
  last_contact_at timestamp with time zone,
  next_contact_at timestamp with time zone,
  notes text
);

-- Create views for easy monitoring
create view agent_performance as
select 
  agent_name,
  status,
  tasks_completed,
  error_count,
  case 
    when error_count > 0 then round((error_count::float / nullif(tasks_completed, 0)) * 100, 2)
    else 0 
  end as error_rate_percent,
  last_updated
from agent_status;

create view health_summary as
select 
  health_score,
  mrr,
  churn_rate,
  cash_runway_days,
  cac,
  ltv_cac,
  case 
    when health_score >= 80 then 'optimal'
    when health_score >= 60 then 'yellow'
    when health_score >= 40 then 'red'
    else 'critical'
  end as health_status,
  last_updated
from health_check
where id = 1;