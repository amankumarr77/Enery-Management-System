import { useState, useCallback, useRef, useEffect } from 'react'
import { useWebSocket } from './useWebSocket'

// Base URL
const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

// API + WebSocket URLs (FIXED for production)
const API = BASE_URL

const WS_BASE = BASE_URL.startsWith('https')
  ? BASE_URL.replace('https', 'wss')
  : BASE_URL.replace('http', 'ws')

const WS_URL = `${WS_BASE}/ws/market`

/**
 * Hook for real-time market data with WebSocket price updates.
 */
export function useMarketData() {
  const [currentPrice, setCurrentPrice] = useState(null)
  const [priceHistory, setPriceHistory] = useState([])
  const [stats, setStats] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [priceDirection, setPriceDirection] = useState(null) // 'up', 'down', null

  const prevPriceRef = useRef(null)
  const maxHistory = 500

  // ── WebSocket handler ──
  const handleMessage = useCallback((msg) => {
    if (msg.type === 'price_tick' && msg.data) {
      const tick = msg.data
      const price = tick.price_inr_kwh

      // Direction detection
      if (prevPriceRef.current !== null) {
        if (price > prevPriceRef.current) setPriceDirection('up')
        else if (price < prevPriceRef.current) setPriceDirection('down')
        else setPriceDirection(null)
      }

      prevPriceRef.current = price

      setCurrentPrice(tick)

      setPriceHistory(prev => {
        const next = [...prev, tick]
        return next.length > maxHistory ? next.slice(-maxHistory) : next
      })
    }
  }, [])

  const { isConnected } = useWebSocket(WS_URL, { onMessage: handleMessage })

  // ── Fetch History ──
  const fetchHistory = useCallback(async (hours = 24) => {
    try {
      const res = await fetch(`${API}/api/market/history?hours=${hours}`)
      if (!res.ok) throw new Error('Failed to fetch history')

      const data = await res.json()
      setStats(data)

      if (data.prices) {
        setPriceHistory(data.prices)

        if (data.prices.length > 0) {
          setCurrentPrice(data.prices[data.prices.length - 1])
        }
      }
    } catch (e) {
      console.error('❌ Failed to fetch market history:', e)
    }
  }, [])

  // ── Fetch Forecast ──
  const fetchForecast = useCallback(async (horizon = 24) => {
    try {
      const res = await fetch(`${API}/api/market/forecast?horizon=${horizon}`)
      if (!res.ok) throw new Error('Failed to fetch forecast')

      const data = await res.json()
      setForecast(data)
    } catch (e) {
      console.error('❌ Failed to fetch forecast:', e)
    }
  }, [])

  // ── Initial Load ──
  useEffect(() => {
    fetchHistory(168)
    fetchForecast()

    const interval = setInterval(() => fetchForecast(), 60000)

    return () => clearInterval(interval)
  }, [fetchHistory, fetchForecast])

  return {
    currentPrice,
    priceHistory,
    priceDirection,
    stats,
    forecast,
    isConnected,
    fetchHistory,
    fetchForecast,
  }
}