"use client"

import { useEffect, useRef, useState } from "react"
import { createWebSocket } from "@/lib/api"
import type { WSEvent } from "@/lib/types"

interface UseWebSocketArgs {
  sessionId: string
  enabled?: boolean
  onEvent?: (event: WSEvent) => void
}

export function useWebSocket({
  sessionId,
  enabled = true,
  onEvent,
}: UseWebSocketArgs) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null)
  const onEventRef = useRef(onEvent)
  const retryRef = useRef<number | null>(null)

  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (!enabled || !sessionId || sessionId === "pending") return

    let ws: WebSocket | null = null
    let closed = false

    const connect = () => {
      try {
        ws = createWebSocket(sessionId)
      } catch {
        scheduleRetry()
        return
      }

      ws.onopen = () => setIsConnected(true)

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as WSEvent
          setLastEvent(data)
          onEventRef.current?.(data)
        } catch {
          /* ignore malformed frames */
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        if (!closed) scheduleRetry()
      }

      ws.onerror = () => {
        ws?.close()
      }
    }

    const scheduleRetry = () => {
      if (retryRef.current) window.clearTimeout(retryRef.current)
      retryRef.current = window.setTimeout(connect, 2500)
    }

    connect()

    return () => {
      closed = true
      if (retryRef.current) window.clearTimeout(retryRef.current)
      ws?.close()
    }
  }, [sessionId, enabled])

  return { isConnected, lastEvent }
}
