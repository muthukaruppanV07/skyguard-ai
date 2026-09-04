import { Shield, Zap, Database, Wifi } from 'lucide-react'

export function Header() {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">SKYGUARD AI</h1>
                <p className="text-xs text-gray-500">AWS Intelligent Anomaly Detection</p>
              </div>
            </div>
            <div className="hidden md:flex items-center gap-6 text-sm text-gray-500">
              <span className="flex items-center gap-1"><Database className="w-4 h-4" /> 8 Stations</span>
              <span className="flex items-center gap-1"><Wifi className="w-4 h-4" /> Real-time</span>
              <span className="flex items-center gap-1"><Zap className="w-4 h-4" /> ML Enhanced</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-lg bg-green-50 text-green-700 text-sm font-medium">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              LIVE
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-500">SIH 2024 - PS 26073</p>
              <p className="text-xs text-gray-400">MoES / IMD</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}