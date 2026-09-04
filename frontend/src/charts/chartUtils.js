export const CHART_COLORS = {
  temperature: '#ef4444',
  pressure: '#3b82f6',
  humidity: '#22c55e',
  anomaly: '#f97316',
  grid: '#e5e7eb',
  text: '#6b7280',
}

export const CHART_MARGIN = { top: 10, right: 30, left: 10, bottom: 40 }

export function formatChartData(rawData, valueKey, timeKey = 'timestamp') {
  return rawData
    .filter(d => d[valueKey] !== null && d[valueKey] !== undefined)
    .map(d => ({
      time: new Date(d[timeKey]),
      value: d[valueKey],
      ...d,
    }))
    .sort((a, b) => a.time - b.time)
}

export function getYDomain(data, valueKey, padding = 0.1) {
  const values = data.map(d => d[valueKey]).filter(v => v !== null && v !== undefined)
  if (values.length === 0) return [0, 100]
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min
  return [min - range * padding, max + range * padding]
}

export const SEVERITY_COLORS = {
  NORMAL: '#22c55e',
  LOW: '#84cc16',
  SUSPICIOUS: '#facc15',
  HIGH: '#f97316',
  CRITICAL: '#ef4444',
}

export function getSeverityColor(severity) {
  return SEVERITY_COLORS[severity] || '#22c55e'
}