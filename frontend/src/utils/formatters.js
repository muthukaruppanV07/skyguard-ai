export function formatTemperature(value) {
  return `${value.toFixed(1)}°C`
}

export function formatPressure(value) {
  return `${value.toFixed(1)} hPa`
}

export function formatHumidity(value) {
  return `${value.toFixed(1)}%`
}

export function formatScore(value) {
  return `${value.toFixed(1)}`
}

export function formatConfidence(value) {
  return `${(value * 100).toFixed(1)}%`
}

export function formatTimestamp(isoString) {
  const date = new Date(isoString)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatDateTime(isoString) {
  const date = new Date(isoString)
  return date.toLocaleString([], { 
    month: 'short', 
    day: 'numeric', 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

export function getSeverityClass(severity) {
  const classes = {
    NORMAL: 'badge-normal',
    LOW: 'badge-low',
    SUSPICIOUS: 'badge-suspicious',
    HIGH: 'badge-high',
    CRITICAL: 'badge-critical',
  }
  return classes[severity] || 'badge-normal'
}

export function getSeverityColor(severity) {
  const colors = {
    NORMAL: '#22c55e',
    LOW: '#84cc16',
    SUSPICIOUS: '#facc15',
    HIGH: '#f97316',
    CRITICAL: '#ef4444',
  }
  return colors[severity] || '#22c55e'
}

export function getHealthStatusClass(score) {
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  if (score >= 40) return 'text-orange-600'
  return 'text-red-600'
}

export function getHealthStatusLabel(score) {
  if (score >= 80) return 'HEALTHY'
  if (score >= 60) return 'WARNING'
  if (score >= 40) return 'MAINTENANCE_RECOMMENDED'
  return 'CRITICAL'
}

export function truncateText(text, maxLength = 100) {
  if (!text) return ''
  return text.length > maxLength ? text.slice(0, maxLength) + '...' : text
}

export function formatNumber(value, decimals = 2) {
  if (value === null || value === undefined) return 'N/A'
  return value.toFixed(decimals)
}