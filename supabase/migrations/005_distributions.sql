-- Record of every post the engine publishes to an external channel
create table distributions (
  id uuid primary key default uuid_generate_v4(),
  division_id uuid not null references divisions(id) on delete cascade,
  channel text not null,
  kind text not null check (kind in ('article', 'product')),
  target_url text not null,
  status text not null check (status in ('posted', 'failed')),
  external_ref text,
  error text,
  created_at timestamp with time zone default now()
);
create index idx_distributions_cap on distributions (division_id, channel, created_at desc);

alter table distributions enable row level security;
create policy "authenticated read distributions" on distributions for select to authenticated using (true);
