-- Row Level Security
-- The service-role key (API routes, cron, Python worker) bypasses RLS.
-- Tables with no policy below are inaccessible to anon/authenticated clients.

alter table health_check enable row level security;
alter table agent_status enable row level security;
alter table metrics enable row level security;
alter table analysis_requests enable row level security;
alter table customers enable row level security;
alter table transactions enable row level security;
alter table leads enable row level security;

-- Signed-in users can read system status
create policy "authenticated read health_check" on health_check
  for select to authenticated using (true);
create policy "authenticated read agent_status" on agent_status
  for select to authenticated using (true);
create policy "authenticated read metrics" on metrics
  for select to authenticated using (true);

-- Users manage only their own analysis requests
create policy "own analysis_requests select" on analysis_requests
  for select to authenticated using (user_id = auth.uid());
create policy "own analysis_requests insert" on analysis_requests
  for insert to authenticated with check (user_id = auth.uid() and status = 'pending');

-- Customers see their own record only (matched by email)
create policy "own customer select" on customers
  for select to authenticated using (email = (auth.jwt() ->> 'email'));
create policy "own transactions select" on transactions
  for select to authenticated using (
    customer_id in (select id from customers where email = (auth.jwt() ->> 'email'))
  );

-- Views run with the caller's permissions, so the policies above apply
alter view agent_performance set (security_invoker = true);
alter view health_summary set (security_invoker = true);
