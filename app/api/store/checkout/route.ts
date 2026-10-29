import { NextRequest, NextResponse } from 'next/server'
import { supabase } from '../../../../lib/supabase'
import { stripe } from '../../../../lib/stripe'

// Public: anyone can buy a published product
export async function POST(request: NextRequest) {
  try {
    const { slug } = await request.json()
    const { data: product } = await supabase
      .from('products')
      .select('id, division_id, slug, title, description, price_cents, currency')
      .eq('slug', slug)
      .eq('status', 'published')
      .maybeSingle()
    if (!product) return NextResponse.json({ error: 'Product not found' }, { status: 404 })

    const origin = request.nextUrl.origin
    const session = await stripe.checkout.sessions.create({
      mode: 'payment',
      line_items: [{
        quantity: 1,
        price_data: {
          currency: product.currency,
          unit_amount: product.price_cents,
          product_data: { name: product.title, description: product.description }
        }
      }],
      metadata: { product_id: product.id, division_id: product.division_id },
      payment_intent_data: { metadata: { division_id: product.division_id } },
      success_url: `${origin}/p/${product.slug}?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${origin}/p/${product.slug}`
    })
    return NextResponse.json({ url: session.url })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'error' }, { status: 500 })
  }
}
