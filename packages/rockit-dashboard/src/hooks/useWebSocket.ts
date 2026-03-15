import { useEffect, useRef } from 'react'
import { useMarketStore } from '../store'
import type { LiveSnapshot } from '../types'

/**
 * WebSocket hook — connects to /ws/dashboard and pushes LiveSnapshots to the store.
 * Auto-reconnects with exponential backoff.
 */
export function useWebSocket() {
  const applySnapshot = useMarketStore(s => s.applySnapshot)
  const setConnected = useMarketStore(s => s.setConnected)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(1000)

  useEffect(() => {
    let mounted = true

    function connect() {
      if (!mounted) return

      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${protocol}://${window.location.host}/ws/dashboard`)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        retryRef.current = 1000 // Reset backoff
      }

      ws.onmessage = (event) => {
        try {
          const snap: LiveSnapshot = JSON.parse(event.data)
          applySnapshot(snap)
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onclose = () => {
        setConnected(false)
        if (mounted) {
          setTimeout(connect, retryRef.current)
          retryRef.current = Math.min(retryRef.current * 2, 30000)
        }
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    return () => {
      mounted = false
      wsRef.current?.close()
    }
  }, [applySnapshot, setConnected])
}
