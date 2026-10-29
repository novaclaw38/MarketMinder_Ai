'use client'

import { useState, useEffect, useCallback } from 'react'
import { supabaseBrowser } from '../../lib/supabase-browser'

const TIERS = ['starter', 'professional', 'enterprise']

export default function Dashboard() {
  const [metrics, setMetrics] = useState<any>(null)
  const [analyses, setAnalyses] = useState<any[]>([])
  const [subscription, setSubscription] = useState<any>(null)
  const [divisions, setDivisions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState('')

  // Authenticated fetch; sends the user to /login when there is no valid session
  const api = useCallback(async (path: string, init: RequestInit = {}) => {
    const { data: { session } } = await supabaseBrowser.auth.getSession()
    if (!session) {
      window.location.href = '/login'
      return null
    }
    const res = await fetch(path, {
      ...init,
      headers: { ...init.headers, Authorization: `Bearer ${session.access_token}` }
    })
    if (res.status === 401) {
      window.location.href = '/login'
      return null
    }
    return res
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [m, a, b, d] = await Promise.all([
        api('/api/metrics'), api('/api/analyses'), api('/api/billing'), api('/api/divisions')
      ])
      if (m) setMetrics(await m.json())
      if (a) setAnalyses((await a.json()).analyses ?? [])
      if (b) setSubscription((await b.json()).subscription)
      if (d) setDivisions((await d.json()).divisions ?? [])
    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 30000)
    const billing = new URLSearchParams(window.location.search).get('billing')
    if (billing === 'success') setNotice('Subscription started. It may take a moment to appear.')
    if (billing === 'canceled') setNotice('Checkout canceled.')
    return () => clearInterval(interval)
  }, [refresh])

  const submitAnalysis = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setNotice('')
    try {
      const res = await api('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      })
      if (res && !res.ok) setNotice((await res.json()).error ?? 'Analysis failed')
      else setQuery('')
      await refresh()
    } finally {
      setSubmitting(false)
    }
  }

  const subscribe = async (tier: string) => {
    const res = await api('/api/billing/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tier })
    })
    if (!res) return
    const data = await res.json()
    if (data.url) window.location.href = data.url
    else setNotice(data.error ?? 'Could not start checkout')
  }

  const signOut = async () => {
    await supabaseBrowser.auth.signOut()
    window.location.href = '/login'
  }

  const money = (cents: number = 0) => `${cents < 0 ? '-' : ''}$${(Math.abs(cents) / 100).toFixed(2)}`
  const timeLeft = (deadline: string) => {
    const ms = new Date(deadline).getTime() - Date.now()
    if (ms <= 0) return 'deadline reached'
    const h = Math.floor(ms / 3_600_000)
    return `${Math.floor(h / 24)}d ${h % 24}h left`
  }

  const getStatusColor = (score: number) => {
    if (score >= 70) return 'text-green-600'
    if (score >= 40) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getHealthLabel = (score: number) => {
    if (score >= 80) return 'Optimal'
    if (score >= 60) return 'Yellow'
    if (score >= 40) return 'Red'
    return 'Critical'
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading MarketMinder AI...</p>
        </div>
      </div>
    )
  }

  const health = metrics?.health_score ?? 0
  const agents: any[] = metrics?.agents ?? []
  const activeAgents = agents.filter((a) => a.status === 'processing' || a.status === 'idle').length
  const subscribed = subscription && subscription.subscription_status !== 'canceled'

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">MarketMinder AI</h1>
            <p className="text-gray-600">Mission Control Dashboard</p>
          </div>
          <button onClick={signOut} className="text-sm text-gray-600 hover:text-gray-900">Sign out</button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8 space-y-8">
        {notice && <div className="bg-blue-50 text-blue-800 rounded-lg p-3 text-sm">{notice}</div>}

        <div>
          <div className={`text-4xl font-bold ${getStatusColor(health)}`}>{health.toFixed(1)}</div>
          <div className="text-gray-600">Health Score - {getHealthLabel(health)}</div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">MRR</div>
            <div className="text-2xl font-bold text-gray-900">${(metrics?.mrr ?? 0).toLocaleString()}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">Churn Rate</div>
            <div className={`text-2xl font-bold ${getStatusColor(100 - (metrics?.churn_rate ?? 0) * 1000)}`}>
              {((metrics?.churn_rate ?? 0) * 100).toFixed(1)}%
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">Cash Runway</div>
            <div className="text-2xl font-bold text-gray-900">{metrics?.cash_runway ?? 0} days</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">Active Agents</div>
            <div className="text-2xl font-bold text-gray-900">{activeAgents}/{agents.length}</div>
          </div>
        </div>

        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-1">Divisions</h2>
          <p className="text-sm text-gray-500 mb-4">
            Each division is its own business with agents, a budget and a P&amp;L. It must turn a profit within its
            window or it is deleted.
          </p>
          {divisions.length === 0 && (
            <p className="text-sm text-gray-500">No divisions yet. The venture engine launches them when the worker is running.</p>
          )}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {divisions.map((d) => (
              <div key={d.id} className={`bg-white rounded-lg shadow p-6 ${d.status === 'deleted' ? 'opacity-60' : ''}`}>
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-bold text-gray-900">{d.name}</h3>
                    <p className="text-sm text-gray-500">{d.thesis}</p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${
                    d.status === 'active' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'
                  }`}>
                    {d.status === 'active' ? `cycle ${d.cycle} · ${timeLeft(d.deadline)}` : 'deleted'}
                  </span>
                </div>
                {d.end_reason && <p className="mt-2 text-sm text-red-600">{d.end_reason}</p>}
                <div className="grid grid-cols-4 gap-2 mt-4 text-sm">
                  <div><div className="text-gray-500">Revenue</div><div className="font-medium">{money(d.pnl?.revenue_cents)}</div></div>
                  <div><div className="text-gray-500">Refunds</div><div className="font-medium">{money(d.pnl?.refund_cents)}</div></div>
                  <div><div className="text-gray-500">Costs</div>
                    <div className="font-medium">{money(d.pnl?.cost_cents)} / {money(d.budget_cents)}</div></div>
                  <div><div className="text-gray-500">Profit</div>
                    <div className={`font-bold ${(d.pnl?.profit_cents ?? 0) > 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {money(d.pnl?.profit_cents)}</div></div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {d.agents.map((a: any) => (
                    <span key={a.id} className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700">
                      {a.role} · {a.tasks_completed}
                    </span>
                  ))}
                </div>
                {d.products.map((p: any) => (
                  <a key={p.slug} href={`/p/${p.slug}`} className="block mt-3 text-sm underline">
                    {p.title} ({money(p.price_cents)})
                  </a>
                ))}
                <ul className="mt-4 space-y-1 text-xs text-gray-600">
                  {d.activity.map((a: any) => (
                    <li key={a.id}>
                      <span className="text-gray-400">{new Date(a.created_at).toLocaleString()}</span>{' '}
                      <span className="font-medium">{a.agent_role}</span>: {a.summary}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Billing</h2>
          {subscribed ? (
            <p className="text-gray-700">
              <span className="capitalize font-medium">{subscription.subscription_tier}</span> plan ·{' '}
              {subscription.subscription_status}
              {subscription.current_period_end &&
                ` · renews ${new Date(subscription.current_period_end).toLocaleDateString()}`}
            </p>
          ) : (
            <div className="flex flex-wrap gap-3">
              {TIERS.map((tier) => (
                <button key={tier} onClick={() => subscribe(tier)}
                  className="px-4 py-2 rounded bg-blue-600 text-white capitalize hover:bg-blue-700">
                  Subscribe: {tier}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Market Analysis</h2>
          <form onSubmit={submitAnalysis} className="flex gap-3 mb-4">
            <input className="flex-1 border rounded p-2" placeholder="What market question should we analyze?"
              value={query} onChange={(e) => setQuery(e.target.value)} required />
            <button disabled={submitting} className="px-4 py-2 rounded bg-black text-white disabled:opacity-50">
              {submitting ? 'Analyzing...' : 'Analyze'}
            </button>
          </form>
          <div className="space-y-3">
            {analyses.length === 0 && <p className="text-sm text-gray-500">No analyses yet.</p>}
            {analyses.map((a) => (
              <details key={a.id} className="border rounded-lg p-4">
                <summary className="cursor-pointer flex justify-between">
                  <span className="text-gray-900">{a.query}</span>
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    a.status === 'completed' ? 'bg-green-100 text-green-600' :
                    a.status === 'failed' ? 'bg-red-100 text-red-600' : 'bg-yellow-100 text-yellow-600'
                  }`}>{a.status}</span>
                </summary>
                <div className="mt-3 text-sm text-gray-700 space-y-2">
                  {a.error_message && <p className="text-red-600">{a.error_message}</p>}
                  {a.result?.summary && <p>{a.result.summary}</p>}
                  {['opportunities', 'risks', 'next_steps'].map((k) =>
                    a.result?.[k]?.length ? (
                      <div key={k}>
                        <div className="font-medium capitalize">{k.replace('_', ' ')}</div>
                        <ul className="list-disc ml-5">
                          {a.result[k].map((item: string, i: number) => <li key={i}>{item}</li>)}
                        </ul>
                      </div>
                    ) : null
                  )}
                </div>
              </details>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">AI Agents</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <div key={agent.agent_name} className="border rounded-lg p-4">
                <div className="flex justify-between items-start">
                  <h3 className="font-medium text-gray-900 capitalize">{agent.agent_name.replace(/_/g, ' ')}</h3>
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    agent.status === 'processing' ? 'bg-blue-100 text-blue-600' :
                    agent.status === 'idle' ? 'bg-green-100 text-green-600' :
                    'bg-yellow-100 text-yellow-600'
                  }`}>{agent.status}</span>
                </div>
                <div className="mt-2 text-sm text-gray-500">
                  Tasks: {agent.tasks_completed || 0} | Errors: {agent.error_count || 0}
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}
