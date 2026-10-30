import { createClient, SupabaseClient } from '@supabase/supabase-js'

let client: SupabaseClient | undefined

// Created on first use, so a build without Supabase env vars (e.g. a Vercel preview
// scope that lacks them) can still compile and collect page data.
export const supabase: SupabaseClient = new Proxy({} as SupabaseClient, {
  get(_target, prop) {
    client ??= createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    )
    const value = (client as any)[prop]
    return typeof value === 'function' ? value.bind(client) : value
  }
})
