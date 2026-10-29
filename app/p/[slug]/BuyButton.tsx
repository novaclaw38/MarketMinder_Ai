'use client'

import { useState } from 'react'

export default function BuyButton({ slug, label }: { slug: string; label: string }) {
  const [error, setError] = useState('')

  const buy = async () => {
    const res = await fetch('/api/store/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug })
    })
    const data = await res.json()
    if (data.url) window.location.href = data.url
    else setError(data.error ?? 'Could not start checkout')
  }

  return (
    <div>
      <button onClick={buy} className="px-5 py-3 rounded bg-black text-white">{label}</button>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  )
}
