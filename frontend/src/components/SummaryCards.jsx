import { Users, CheckCircle, AlertTriangle, XCircle, Activity, HeartPulse } from 'lucide-react'

const cards = [
  { key: 'totalStations', label: 'Total Stations', icon: Users, color: 'bg-blue-500', trend: null },
  { key: 'healthyStations', label: 'Healthy', icon: CheckCircle, color: 'bg-green-500', trend: 'up' },
  { key: 'warningStations', label: 'Warning', icon: AlertTriangle, color: 'bg-yellow-500', trend: null },
  { key: 'criticalStations', label: 'Critical', icon: XCircle, color: 'bg-red-500', trend: 'down' },
  { key: 'activeAnomalies', label: 'Active Anomalies', icon: Activity, color: 'bg-orange-500', trend: 'up' },
  { key: 'avgNetworkHealth', label: 'Avg Network Health', icon: HeartPulse, color: 'bg-purple-500', trend: null, suffix: '%' },
]

export function SummaryCards({ data }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {cards.map((card) => {
        const value = data?.[card.key] ?? 0
        const Icon = card.icon
        return (
          <div key={card.key} className="card hover:shadow-card-hover transition-shadow">
            <div className="card-body">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">{card.label}</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {typeof value === 'number' ? (card.suffix ? `${value.toFixed(1)}${card.suffix}` : value.toLocaleString()) : value}
                  </p>
                </div>
                <div className={`w-10 h-10 rounded-lg ${card.color} flex items-center justify-center`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}