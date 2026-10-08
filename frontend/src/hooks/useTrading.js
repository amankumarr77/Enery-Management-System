import { useState, useCallback, useEffect } from 'react'
import { useWebSocket } from './useWebSocket'

const API = 'http://127.0.0.1:8000'
const WS_URL = 'ws://127.0.0.1:8000/ws/trading'

/**
 * Hook for trading operations: orders, trades, position, and engine control.
 */
export function useTrading() {
  const [orders, setOrders] = useState([])
  const [trades, setTrades] = useState([])
  const [position, setPosition] = useState(null)
  const [tradingStatus, setTradingStatus] = useState(null)
  const [riskLimits, setRiskLimits] = useState(null)
  const [alerts, setAlerts] = useState([])

  const handleMessage = useCallback((msg) => {
    switch (msg.type) {
      case 'order_update':
        setOrders(prev => {
          const idx = prev.findIndex(o => o.id === msg.data.id)
          if (idx >= 0) {
            const next = [...prev]
            next[idx] = { ...next[idx], ...msg.data }
            return next
          }
          return [msg.data, ...prev]
        })
        break
      case 'trade_fill':
        setTrades(prev => [msg.data, ...prev].slice(0, 200))
        break
      case 'position_update':
        setPosition(msg.data)
        break
      case 'alert':
        setAlerts(prev => [{ ...msg.data, id: Date.now(), timestamp: msg.timestamp }, ...prev].slice(0, 50))
        break
    }
  }, [])

  const { isConnected } = useWebSocket(WS_URL, { onMessage: handleMessage })

  // ── REST API calls ──

  const fetchOrders = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/orders?limit=100`)
      const data = await res.json()
      setOrders(data)
    } catch (e) { console.error('Failed to fetch orders:', e) }
  }, [])

  const fetchTrades = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/trades?limit=100`)
      const data = await res.json()
      setTrades(data)
    } catch (e) { console.error('Failed to fetch trades:', e) }
  }, [])

  const fetchPosition = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/position`)
      const data = await res.json()
      setPosition(data)
    } catch (e) { console.error('Failed to fetch position:', e) }
  }, [])

  const fetchTradingStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/trading/status`)
      const data = await res.json()
      setTradingStatus(data)
    } catch (e) { console.error('Failed to fetch trading status:', e) }
  }, [])

  const fetchRiskLimits = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/risk/limits`)
      const data = await res.json()
      setRiskLimits(data)
    } catch (e) { console.error('Failed to fetch risk limits:', e) }
  }, [])

  const placeOrder = useCallback(async (orderData) => {
    try {
      const res = await fetch(`${API}/api/orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData),
      })
      const data = await res.json()
      if (res.ok) {
        fetchOrders()
        fetchPosition()
        fetchTrades()
      }
      return data
    } catch (e) {
      console.error('Failed to place order:', e)
      return null
    }
  }, [fetchOrders, fetchPosition, fetchTrades])

  const cancelOrder = useCallback(async (orderId) => {
    try {
      const res = await fetch(`${API}/api/orders/${orderId}`, { method: 'DELETE' })
      if (res.ok) fetchOrders()
    } catch (e) { console.error('Failed to cancel order:', e) }
  }, [fetchOrders])

  const startTrading = useCallback(async (strategy = 'AUTO_CVAR') => {
    try {
      const res = await fetch(`${API}/api/trading/start?strategy=${strategy}`, { method: 'POST' })
      const data = await res.json()
      setTradingStatus(data)
      return data
    } catch (e) { console.error('Failed to start trading:', e) }
  }, [])

  const stopTrading = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/trading/stop`, { method: 'POST' })
      const data = await res.json()
      setTradingStatus(data)
      return data
    } catch (e) { console.error('Failed to stop trading:', e) }
  }, [])

  const updateSettings = useCallback(async (settings) => {
    try {
      const res = await fetch(`${API}/api/trading/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      return await res.json()
    } catch (e) { console.error('Failed to update settings:', e) }
  }, [])

  const dismissAlert = useCallback((alertId) => {
    setAlerts(prev => prev.filter(a => a.id !== alertId))
  }, [])

  // Fetch initial data on mount
  useEffect(() => {
    fetchOrders()
    fetchTrades()
    fetchPosition()
    fetchTradingStatus()
    fetchRiskLimits()
    // Refresh position & status periodically
    const interval = setInterval(() => {
      fetchPosition()
      fetchTradingStatus()
      fetchRiskLimits()
    }, 10000)
    return () => clearInterval(interval)
  }, [fetchOrders, fetchTrades, fetchPosition, fetchTradingStatus, fetchRiskLimits])

  return {
    orders,
    trades,
    position,
    tradingStatus,
    riskLimits,
    alerts,
    isConnected,
    placeOrder,
    cancelOrder,
    startTrading,
    stopTrading,
    updateSettings,
    fetchOrders,
    fetchTrades,
    fetchPosition,
    dismissAlert,
  }
}
