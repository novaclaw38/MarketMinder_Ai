import { MetadataRoute } from 'next'
import { supabase } from '../lib/supabase'

export const dynamic = 'force-dynamic'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const site = (process.env.SITE_URL || '').replace(/\/$/, '')
  if (!site) return []

  const [products, articles] = await Promise.all([
    supabase.from('products').select('slug, created_at').eq('status', 'published'),
    supabase.from('articles').select('slug, created_at').eq('status', 'published')
  ])

  return [
    ...(products.data ?? []).map((p) => ({ url: `${site}/p/${p.slug}`, lastModified: p.created_at })),
    ...(articles.data ?? []).map((a) => ({ url: `${site}/blog/${a.slug}`, lastModified: a.created_at }))
  ]
}
