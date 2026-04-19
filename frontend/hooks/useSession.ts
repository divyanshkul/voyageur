"use client"

import { useCallback, useEffect, useState } from "react"
import type {
  CallResult,
  Hotel,
  LiveCall,
  Report,
  SessionState,
  Stage,
  TravelPreferences,
} from "@/lib/types"

const emptyState = (session_id: string): SessionState => ({
  session_id,
  stage: "collecting",
  preferences: null,
  hotels: [],
  approved_hotels: [],
  call_results: [],
  report: null,
})

export function useSession() {
  const [session, setSession] = useState<SessionState>(() =>
    emptyState("pending")
  )
  const [liveCalls, setLiveCalls] = useState<LiveCall[]>([])

  useEffect(() => {
    const id = crypto.randomUUID()
    setSession((s) => ({ ...s, session_id: id }))
  }, [])

  const updateStage = useCallback((stage: Stage) => {
    setSession((s) => ({ ...s, stage }))
  }, [])

  const setPreferences = useCallback((preferences: TravelPreferences) => {
    setSession((s) => ({ ...s, preferences }))
  }, [])

  const setHotels = useCallback((hotels: Hotel[]) => {
    setSession((s) => ({ ...s, hotels }))
  }, [])

  const setApprovedHotels = useCallback((approved_hotels: Hotel[]) => {
    setSession((s) => ({ ...s, approved_hotels }))
    setLiveCalls(
      approved_hotels.map((h) => ({
        hotel_name: h.name,
        phone: h.phone,
        status: "queued",
        duration: 0,
        price: null,
        available: null,
      }))
    )
  }, [])

  const addCallResult = useCallback((result: CallResult) => {
    setSession((s) => ({ ...s, call_results: [...s.call_results, result] }))
  }, [])

  const setReport = useCallback((report: Report) => {
    setSession((s) => ({ ...s, report }))
  }, [])

  const upsertLiveCall = useCallback(
    (hotel_name: string, patch: Partial<LiveCall>) => {
      setLiveCalls((calls) => {
        const existing = calls.find((c) => c.hotel_name === hotel_name)
        if (existing) {
          return calls.map((c) =>
            c.hotel_name === hotel_name ? { ...c, ...patch } : c
          )
        }
        return [
          ...calls,
          {
            hotel_name,
            status: "queued",
            duration: 0,
            price: null,
            available: null,
            ...patch,
          } as LiveCall,
        ]
      })
    },
    []
  )

  return {
    session,
    liveCalls,
    updateStage,
    setPreferences,
    setHotels,
    setApprovedHotels,
    addCallResult,
    setReport,
    upsertLiveCall,
  }
}
