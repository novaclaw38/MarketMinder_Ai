'use client'

import { useState, useEffect } from 'react'

export default function Dashboard() {
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchMetrics()
    const interval = setInterval(fetchMetrics, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchMetrics = async () => {
    try {
      const res = await fetch('/api/metrics')
      const data = await res.json()
      setMetrics(data)
    } catch (error) {
      console.error('Error fetching metrics:', error)
    } finally {
      setLoading(false)
    }
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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">MarketMinder AI</h1>
          <p className="text-gray-600">Mission Control Dashboard</p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <div className={`text-4xl font-bold ${getStatusColor(metrics?.health_score || 0)}`}>
            {metrics?.health_score.toFixed(1) || 0}
          </div>
          <div className="text-gray-600">Health Score - {getHealthLabel(metrics?.health_score || 0)}</div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">MRR</div>
            <div className="text-2xl font-bold text-gray-900">
              ${metrics?.mrr.toLocaleString() || 0}
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">Churn Rate</div>
            <div className={`text-2xl font-bold ${getStatusColor((metrics?.churn_rate || 0) * 100)}`}>
              {(metrics?.churn_rate || 0) * 100}%
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">Cash Runway</div>
            <div className="text-2xl font-bold text-gray-900">
              {metrics?.cash_runway || 0} days
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500">Active Agents</div>
            <div className="text-2xl font-bold text-gray-900">
              {metrics?.agents?.filter((a: any) => a.status === 'processing' || a.status === 'idle').length || 0}/6
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">AI Agents</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {metrics?.agents?.map((agent: any) => (
              <div key={agent.agent_name} className="border rounded-lg p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-medium text-gray-900 capitalize">
                      {agent.agent_name.replace('_', ' ')}
                    </h3>
                  </div>
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    agent.status === 'processing' ? 'bg-blue-100 text-blue-600' :
                    agent.status === 'idle' ? 'bg-green-100 text-green-600' :
                    'bg-yellow-100 text-yellow-600'
                  }`}>
                    {agent.status}
                  </span>
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