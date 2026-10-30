import { createClient, SupabaseClient } from '@supabase/supabase-js'

let client: SupabaseClient | undefined

// Created on first use so prerendering /dashboard and /login does not need the env vars at build time.
export const supabaseBrowser: SupabaseClient = new Proxy({} as SupabaseClient, {
  get(_target, prop) {
    client ??= createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    )
    const value = (client as any)[prop]
    return typeof value === 'function' ? value.bind(client) : value
  }
})
