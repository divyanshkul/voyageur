"use client"

import { useCallback, useState } from "react"
import { sendMessage as apiSendMessage } from "@/lib/api"
import type { ChatMessage } from "@/lib/types"

interface UseChatArgs {
  sessionId: string
  onStage?: (stage: string) => void
  onHotels?: (hotels: ChatMessage["hotels"]) => void
  onReport?: (report: NonNullable<ChatMessage["report"]>) => void
}

const INTRO: ChatMessage = {
  id: "intro",
  role: "agent",
  content:
    "Bonjour. I'm Voyageur — your AI concierge. Tell me where you're headed, when, and what you're looking for. I'll ring the hotels directly and bring back the real prices.",
  timestamp: new Date(),
}

export function useChat({ sessionId, onStage, onHotels, onReport }: UseChatArgs) {
  const [messages, setMessages] = useState<ChatMessage[]>([INTRO])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || !sessionId || sessionId === "pending") return

      // Replace internal formats with user-friendly text
      const displayText = trimmed.startsWith("APPROVE_IDS:")
        ? "Call the selected hotels"
        : trimmed.startsWith("DEMO_CALL:")
          ? "Demo: Call the top hotel"
          : trimmed

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: displayText,
        timestamp: new Date(),
      }
      setMessages((m) => [...m, userMsg])
      setIsLoading(true)
      setError(null)

      try {
        const resp = await apiSendMessage(sessionId, trimmed)
        const agentMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: "agent",
          content: resp.reply ?? "",
          timestamp: new Date(),
          hotels: resp.hotels ?? undefined,
          report: resp.report ?? undefined,
        }
        setMessages((m) => [...m, agentMsg])
        if (resp.stage) onStage?.(resp.stage)
        if (resp.hotels) onHotels?.(resp.hotels)
        if (resp.report) onReport?.(resp.report)
      } catch (e) {
        const msg = e instanceof Error ? e.message : "unknown error"
        setError(msg)
        setMessages((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: "agent",
            content:
              "The line went quiet — I couldn't reach the concierge desk. Try again in a moment.",
            timestamp: new Date(),
          },
        ])
      } finally {
        setIsLoading(false)
      }
    },
    [sessionId, onStage, onHotels, onReport]
  )

  const appendAgent = useCallback(
    (content: string, extras?: Partial<ChatMessage>) => {
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "agent",
          content,
          timestamp: new Date(),
          ...extras,
        },
      ])
    },
    []
  )

  return { messages, isLoading, error, sendMessage, appendAgent }
}
