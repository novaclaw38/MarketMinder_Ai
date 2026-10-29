import { NextRequest, NextResponse } from 'next/server'
import { supabase } from '../../../../lib/supabase'
import { requireUser } from '../../../../lib/auth'
import { stripe, PRICE_IDS, Tier } from '../../../../lib/stripe'

export async function POST(request: NextRequest) {
  const auth = await requireUser(request)
  if (auth.error) return auth.error

  try {
    const { tier } = await request.json()
    const price = PRICE_IDS[tier as Tier]
    if (!price) return NextResponse.json({ error: 'Unknown or unconfigured tier' }, { status: 400 })

    const email = auth.user.email!
    const { data: existing } = await supabase
      .from('customers')
      .select('stripe_customer_id')
      .eq('email', email)
      .maybeSingle()

    const origin = request.nextUrl.origin
    const session = await stripe.checkout.sessions.create({
      mode: 'subscription',
      line_items: [{ price, quantity: 1 }],
      ...(existing?.stripe_customer_id
        ? { customer: existing.stripe_customer_id }
        : { customer_email: email }),
      client_reference_id: auth.user.id,
      success_url: `${origin}/dashboard?billing=success`,
      cancel_url: `${origin}/dashboard?billing=canceled`
    })

    return NextResponse.json({ url: session.url })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'error' }, { status: 500 })
  }
}
