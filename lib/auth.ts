import { NextRequest, NextResponse } from 'next/server'
import { supabase } from './supabase'

const unauthorized = () => NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

// Verifies the Supabase access token in the Authorization header.
export async function requireUser(request: NextRequest) {
  const token = request.headers.get('authorization')?.replace(/^Bearer /, '')
  if (!token) return { error: unauthorized() }
  const { data, error } = await supabase.auth.getUser(token)
  if (error || !data.user) return { error: unauthorized() }
  return { user: data.user }
}

// For machine callers (cron, worker, admin tooling).
export function hasServiceSecret(request: NextRequest) {
  const secret = process.env.CRON_SECRET
  return !!secret && request.headers.get('authorization') === `Bearer ${secret}`
}
