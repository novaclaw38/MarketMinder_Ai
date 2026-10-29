-- Prevent duplicate transactions when Stripe retries webhook deliveries
create unique index if not exists idx_transactions_stripe_invoice
  on transactions (stripe_invoice_id) where stripe_invoice_id is not null;
