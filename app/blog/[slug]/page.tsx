import Link from 'next/link'
import { supabase } from '../../../lib/supabase'

export const dynamic = 'force-dynamic'

export default async function Article({ params }: { params: { slug: string } }) {
  const { data: article } = await supabase
    .from('articles')
    .select('title, body, products(slug, title)')
    .eq('slug', params.slug)
    .eq('status', 'published')
    .maybeSingle()
  if (!article) return <main className="p-8">Article not found.</main>

  const product = Array.isArray(article.products) ? article.products[0] : article.products

  return (
    <main className="max-w-2xl mx-auto p-8 space-y-6">
      <h1 className="text-3xl font-bold">{article.title}</h1>
      <article className="whitespace-pre-wrap">{article.body}</article>
      <p className="text-sm text-gray-500">This article was written by AI.</p>
      {product && (
        <Link href={`/p/${product.slug}`} className="underline">
          {product.title}
        </Link>
      )}
    </main>
  )
}
