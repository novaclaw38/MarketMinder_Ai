import Stripe from 'stripe'
import { supabase } from './supabase'

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '')

export type Tier = 'starter' | 'professional' | 'enterprise'

export const PRICE_IDS: Record<Tier, string | undefined> = {
  starter: process.env.STRIPE_PRICE_STARTER,
  professional: process.env.STRIPE_PRICE_PROFESSIONAL,
  enterprise: process.env.STRIPE_PRICE_ENTERPRISE
}

export function tierForPrice(priceId?: string): Tier {
  const match = (Object.keys(PRICE_IDS) as Tier[]).find((t) => PRICE_IDS[t] === priceId)
  return match ?? 'starter'
}

// customers.subscription_status only allows a subset of Stripe's statuses
export function mapStatus(status: Stripe.Subscription.Status) {
  switch (status) {
    case 'active':
    case 'trialing':
    case 'past_due':
    case 'incomplete':
      return status
    default:
      return 'canceled'
  }
}

// Monthly recurring revenue in dollars for a subscription
export function subscriptionMrr(sub: Stripe.Subscription) {
  return sub.items.data.reduce((sum, item) => {
    const amount = ((item.price.unit_amount ?? 0) / 100) * (item.quantity ?? 1)
    const { interval, interval_count } = item.price.recurring ?? { interval: 'month', interval_count: 1 }
    const months = interval === 'year' ? 12 * interval_count : interval === 'month' ? interval_count : 1
    return sum + amount / months
  }, 0)
}

// Recompute total MRR from active customers into metrics and health_check
export async function refreshMrr() {
  const { data } = await supabase
    .from('customers')
    .select('mrr')
    .in('subscription_status', ['active', 'trialing', 'past_due'])
  const mrr = (data ?? []).reduce((s, c) => s + (c.mrr ?? 0), 0)
  const now = new Date().toISOString()
  await supabase.from('metrics').update({ value: mrr, last_updated: now }).eq('metric_name', 'mrr')
  await supabase.from('health_check').update({ mrr, last_updated: now }).eq('id', 1)
}
