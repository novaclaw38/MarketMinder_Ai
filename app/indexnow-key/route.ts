// Serves the IndexNow verification key (keyLocation) as plain text
export const dynamic = 'force-dynamic'

export function GET() {
  const key = process.env.INDEXNOW_KEY
  if (!key) return new Response('Not found', { status: 404 })
  return new Response(key, { headers: { 'Content-Type': 'text/plain' } })
}
