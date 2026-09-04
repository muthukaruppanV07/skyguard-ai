import { X, AlertTriangle, Info } from 'lucide-react'
import { formatDateTime, getSeverityColor } from '../utils/formatters'

export function AlertBanner({ alerts, onDismiss, onAcknowledge }) {
  if (!alerts || alerts.length === 0) return null

  const criticalAlerts = alerts.filter(a => a.severity === 'CRITICAL')
  const warningAlerts = alerts.filter(a => a.severity === 'HIGH' || a.severity === 'SUSPICIOUS')

  const displayAlerts = [...criticalAlerts, ...warningAlerts].slice(0, 3)

  return (
    <div className="fixed top-16 left-6 right-6 z-50 space-y-2 pointer-events-none">
      {displayAlerts.map((alert) => (
        <div
          key={alert.id}
          className="pointer-events-auto animate-slide-in bg-white border-l-4 shadow-lg rounded-r-lg"
          style={{ borderColor: getSeverityColor(alert.severity) }}
        >
          <div className="p-4 flex items-start gap-3">
            <div className="flex-shrink-0 mt-0.5">
              {alert.severity === 'CRITICAL' ? (
                <AlertTriangle className="w-5 h-5 text-red-500" />
              ) : (
                <Info className="w-5 h-5 text-orange-500" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <p className="font-medium text-gray-900">{alert.message}</p>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">
                    {alert.timestamp ? formatDateTime(alert.timestamp) : ''}
                  </span>
                  {!alert.acknowledged && (
                    <button
                      onClick={() => onAcknowledge?.(alert.id)}
                      className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                    >
                      Acknowledge
                    </button>
                  )}
                  <button
                    onClick={() => onDismiss?.(alert.id)}
                    className="p-1 text-gray-400 hover:text-gray-600"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Station: {alert.station_id} • Severity: {alert.severity}
              </p>
            </div>
          </div>
        </div>
      ))}
      <style jsx>{`
        @keyframes slide-in {
          from { opacity: 0; transform: translateX(100%); }
          to { opacity: 1; transform: translateX(0); }
        }
        .animate-slide-in { animation: slide-in 0.3s ease-out; }
      `}</style>
    </div>
  )
}