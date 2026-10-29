'use client'

import { useState } from 'react'
import { supabaseBrowser } from '../../lib/supabase-browser'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const signIn = async (e: React.FormEvent) => {
    e.preventDefault()
    const { error } = await supabaseBrowser.auth.signInWithPassword({ email, password })
    if (error) setError(error.message)
    else window.location.href = '/dashboard'
  }

  return (
    <main className="min-h-screen flex items-center justify-center">
      <form onSubmit={signIn} className="w-80 space-y-3">
        <h1 className="text-xl font-semibold">Sign in</h1>
        <input className="w-full border p-2 rounded" type="email" placeholder="Email"
          value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input className="w-full border p-2 rounded" type="password" placeholder="Password"
          value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button className="w-full bg-black text-white p-2 rounded" type="submit">Sign in</button>
      </form>
    </main>
  )
}
