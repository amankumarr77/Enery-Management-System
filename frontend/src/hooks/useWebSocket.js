import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * Custom WebSocket hook with auto-reconnect and message routing.
 */
export function useWebSocket(url, { onMessage, autoConnect = true } = {}) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const pingTimer = useRef(null)
  const onMessageRef = useRef(onMessage)

  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        setIsConnected(true)
        // Start ping interval
        pingTimer.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping')
          }
        }, 30000)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'pong') return
          setLastMessage(data)
          if (onMessageRef.current) {
            onMessageRef.current(data)
          }
        } catch (e) {
          // Non-JSON message
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        clearInterval(pingTimer.current)
        // Auto-reconnect after 3 seconds
        reconnectTimer.current = setTimeout(() => {
          connect()
        }, 3000)
      }

      ws.onerror = () => {
        ws.close()
      }

      wsRef.current = ws
    } catch (e) {
      // Connection failed, retry
      reconnectTimer.current = setTimeout(connect, 5000)
    }
  }, [url])

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current)
    clearInterval(pingTimer.current)
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  useEffect(() => {
    if (autoConnect) connect()
    return () => disconnect()
  }, [autoConnect, connect, disconnect])

  return { isConnected, lastMessage, connect, disconnect }
}
