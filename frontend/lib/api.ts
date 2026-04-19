import type { CallResult, Hotel, Report, Stage, TravelPreferences } from "./types"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export interface ChatResponse {
  reply: string
  stage: Stage
  hotels: Hotel[] | null
  call_progress: CallResult[] | null
  report: Report | null
}

export interface StatusResponse {
  stage: Stage
  preferences: TravelPreferences | null
  hotel_count: number
  approved_count: number
  call_results: Array<{
    hotel_name: string
    status: string
    price: number | null
  }>
  report: Report | null
}

export async function sendMessage(
  sessionId: string,
  message: string
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`chat ${res.status}`)
  return res.json()
}

export async function getStatus(sessionId: string): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE}/api/status/${sessionId}`)
  if (!res.ok) throw new Error(`status ${res.status}`)
  return res.json()
}

export function createWebSocket(sessionId: string): WebSocket {
  const wsBase = API_BASE.replace(/^http/, "ws")
  return new WebSocket(`${wsBase}/ws/${sessionId}`)
}

export { API_BASE };
