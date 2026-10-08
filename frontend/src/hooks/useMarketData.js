import { useState, useCallback, useRef, useEffect } from 'react'
import { useWebSocket } from './useWebSocket'

const API = 'http://127.0.0.1:8000'
const WS_URL = 'ws://127.0.0.1:8000/ws/market'

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

  const handleMessage = useCallback((msg) => {
    if (msg.type === 'price_tick' && msg.data) {
      const tick = msg.data
      const price = tick.price_inr_kwh

      // Determine direction
      if (prevPriceRef.current !== null) {
        setPriceDirection(price > prevPriceRef.current ? 'up' : price < prevPriceRef.current ? 'down' : null)
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

  // Fetch initial data via REST
  const fetchHistory = useCallback(async (hours = 24) => {
    try {
      const res = await fetch(`${API}/api/market/history?hours=${hours}`)
      const data = await res.json()
      setStats(data)
      if (data.prices) {
        setPriceHistory(data.prices)
        if (data.prices.length > 0) {
          setCurrentPrice(data.prices[data.prices.length - 1])
        }
      }
    } catch (e) { console.error('Failed to fetch market history:', e) }
  }, [])

  const fetchForecast = useCallback(async (horizon = 24) => {
    try {
      const res = await fetch(`${API}/api/market/forecast?horizon=${horizon}`)
      const data = await res.json()
      setForecast(data)
    } catch (e) { console.error('Failed to fetch forecast:', e) }
  }, [])

  // Fetch initial data on mount
  useEffect(() => {
    fetchHistory(168)
    fetchForecast()
    // Refresh forecast every 60 seconds
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
