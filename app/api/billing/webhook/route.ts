import { NextRequest, NextResponse } from 'next/server'
import Stripe from 'stripe'
import { supabase } from '../../../../lib/supabase'
import { stripe, tierForPrice, mapStatus, subscriptionMrr, refreshMrr } from '../../../../lib/stripe'

export const dynamic = 'force-dynamic'

async function syncSubscription(sub: Stripe.Subscription) {
  const customerId = typeof sub.customer === 'string' ? sub.customer : sub.customer.id
  const customer = (await stripe.customers.retrieve(customerId)) as Stripe.Customer
  if (customer.deleted || !customer.email) return

  const { error } = await supabase.from('customers').upsert(
    {
      email: customer.email,
      stripe_customer_id: customerId,
      subscription_status: mapStatus(sub.status),
      subscription_tier: tierForPrice(sub.items.data[0]?.price.id),
      mrr: mapStatus(sub.status) === 'canceled' ? 0 : subscriptionMrr(sub),
      current_period_end: new Date(sub.current_period_end * 1000).toISOString(),
      updated_at: new Date().toISOString()
    },
    { onConflict: 'email' }
  )
  if (error) throw error
}

async function recordInvoice(invoice: Stripe.Invoice) {
  const customerId = typeof invoice.customer === 'string' ? invoice.customer : invoice.customer?.id
  const { data: customer } = await supabase
    .from('customers')
    .select('id')
    .eq('stripe_customer_id', customerId ?? '')
    .maybeSingle()

  const { error } = await supabase.from('transactions').insert({
    customer_id: customer?.id ?? null,
    type: 'payment',
    amount_cents: invoice.amount_paid,
    currency: invoice.currency.toUpperCase(),
    status: 'paid',
    stripe_invoice_id: invoice.id,
    description: invoice.description ?? 'Subscription payment'
  })
  // 23505: already recorded (webhook retry)
  if (error && error.code !== '23505') throw error

  if (customer) {
    await supabase
      .from('customers')
      .update({ last_payment_at: new Date().toISOString() })
      .eq('id', customer.id)
  }
}

export async function POST(request: NextRequest) {
  const signature = request.headers.get('stripe-signature')
  const secret = process.env.STRIPE_WEBHOOK_SECRET
  if (!signature || !secret) {
    return NextResponse.json({ error: 'Webhook not configured' }, { status: 400 })
  }

  let event: Stripe.Event
  try {
    event = stripe.webhooks.constructEvent(await request.text(), signature, secret)
  } catch {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 })
  }

  try {
    switch (event.type) {
      case 'checkout.session.completed': {
        const session = event.data.object as Stripe.Checkout.Session
        if (session.mode === 'subscription' && session.subscription) {
          const id = typeof session.subscription === 'string' ? session.subscription : session.subscription.id
          await syncSubscription(await stripe.subscriptions.retrieve(id))
        }
        break
      }
      case 'customer.subscription.created':
      case 'customer.subscription.updated':
      case 'customer.subscription.deleted':
        await syncSubscription(event.data.object as Stripe.Subscription)
        break
      case 'invoice.paid':
        await recordInvoice(event.data.object as Stripe.Invoice)
        break
    }
    await refreshMrr()
    return NextResponse.json({ received: true })
  } catch (error: any) {
    // 500 makes Stripe retry the delivery
    return NextResponse.json({ error: error.message ?? 'error' }, { status: 500 })
  }
}
