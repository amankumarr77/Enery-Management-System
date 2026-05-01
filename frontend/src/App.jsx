import { useState, useEffect } from 'react'
import axios from 'axios'
import Plot from 'react-plotly.js'
import {
  Activity, Battery, DollarSign, Zap, Play, Settings, Database,
  BarChart3, TrendingUp, RefreshCw, Download, Target, Clock,
  PieChart, AlertTriangle
} from 'lucide-react'

import Navbar from './components/Navbar'
import TradingPanel from './components/TradingPanel'
import LiveChart from './components/LiveChart'
import OrderBook from './components/OrderBook'
import PositionTracker from './components/PositionTracker'
import RiskPanel from './components/RiskPanel'

import { useMarketData } from './hooks/useMarketData'
import { useTrading } from './hooks/useTrading'

import './App.css'

// ✅ SINGLE SOURCE OF TRUTH (FIXED)
const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const API = BASE_URL

function App() {
  const [theme, setTheme] = useState(() =>
    localStorage.getItem('emsjb-theme') || 'dark'
  )

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('emsjb-theme', theme)
  }, [theme])

  const toggleTheme = () =>
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'))

  const [activeTab, setActiveTab] = useState('trading')

  // ── Hooks ──
  const {
    currentPrice,
    priceHistory,
    priceDirection,
    stats,
    forecast,
    isConnected: marketConnected,
  } = useMarketData()

  const {
    orders,
    trades,
    position,
    tradingStatus,
    riskLimits,
    alerts,
    isConnected: tradingConnected,
    placeOrder,
    cancelOrder,
    startTrading,
    stopTrading,
    dismissAlert,
  } = useTrading()

  // ── Analytics state ──
  const [config, setConfig] = useState(null)
  const [dataSummary, setDataSummary] = useState(null)
  const [simulationData, setSimulationData] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [baseline, setBaseline] = useState(null)
  const [forecastAcc, setForecastAcc] = useState(null)
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [error, setError] = useState(null)
  const [steps, setSteps] = useState(168)
  const [configEditing, setConfigEditing] = useState(false)
  const [configDraft, setConfigDraft] = useState({})

  useEffect(() => {
    fetchConfig()
    fetchDataSummary()
    fetchHistory()
    fetchForecastAccuracy()
  }, [])

  // ── API calls ──
  const fetchConfig = async () => {
    try {
      const res = await axios.get(`${API}/api/config`)
      setConfig(res.data)
      setConfigDraft(res.data)
    } catch (err) {
      console.error(err)
    }
  }

  const fetchDataSummary = async () => {
    try {
      const res = await axios.get(`${API}/api/data/summary`)
      setDataSummary(res.data)
    } catch (err) {
      console.error(err)
    }
  }

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API}/api/simulation/history`)
      setHistory(res.data)
    } catch (err) {
      console.error(err)
    }
  }

  const fetchForecastAccuracy = async () => {
    try {
      const res = await axios.get(`${API}/api/forecast/accuracy`)
      setForecastAcc(res.data)
    } catch (err) {
      console.error(err)
    }
  }

  const runSimulation = async () => {
    setLoading(true)
    setError(null)

    try {
      const res = await axios.get(`${API}/api/simulation/run?steps=${steps}`)
      setSimulationData(res.data)

      const [metricsRes, baselineRes] = await Promise.all([
        axios.get(`${API}/api/simulation/${res.data.id}/metrics`),
        axios.get(`${API}/api/simulation/${res.data.id}/baseline`),
      ])

      setMetrics(metricsRes.data)
      setBaseline(baselineRes.data)
      fetchHistory()
    } catch {
      setError("Simulation failed.")
    }

    setLoading(false)
  }

  const exportCSV = async (runId) => {
    try {
      const res = await axios.get(
        `${API}/api/simulation/${runId}/export`,
        { responseType: 'blob' }
      )

      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')

      link.href = url
      link.setAttribute('download', `simulation_run_${runId}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      console.error(err)
    }
  }

  const saveConfig = async () => {
    try {
      const res = await axios.post(`${API}/api/config`, configDraft)
      setConfig(res.data)
      setConfigEditing(false)
    } catch (err) {
      console.error(err)
    }
  }

  const inr = (v) =>
    '₹' + Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 })

  const pct = (v) => (v * 100).toFixed(1) + '%'

  return (
    <div className="app-container">
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        marketConnected={marketConnected}
        tradingConnected={tradingConnected}
        currentPrice={currentPrice}
        priceDirection={priceDirection}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      <main className="app-main">
        {/* TRADING TAB */}
        {activeTab === 'trading' && (
          <div className="trading-layout">
            <TradingPanel
              currentPrice={currentPrice}
              priceDirection={priceDirection}
              tradingStatus={tradingStatus}
              position={position}
              onPlaceOrder={placeOrder}
              onStartTrading={startTrading}
              onStopTrading={stopTrading}
            />

            <LiveChart
              priceHistory={priceHistory}
              forecast={forecast}
              theme={theme}
            />

            <OrderBook orders={orders} onCancel={cancelOrder} />

            <PositionTracker position={position} trades={trades} />

            <RiskPanel
              riskLimits={riskLimits}
              alerts={alerts}
              onDismissAlert={dismissAlert}
            />
          </div>
        )}
      </main>
    </div>
  )
}

export default App