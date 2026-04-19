"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { PipelineView } from "@/components/pipeline/PipelineView"
import { ChatPanel } from "@/components/chat/ChatPanel"
import { CallTracker } from "@/components/calling/CallTracker"
import { CompilingView } from "@/components/report/CompilingView"
import { VoiceOnboarding } from "@/components/voice/VoiceOnboarding"
import { useSession } from "@/hooks/useSession"
import { useChat } from "@/hooks/useChat"
import { useWebSocket } from "@/hooks/useWebSocket"
import type { CallStatus, Hotel, Stage, WSEvent } from "@/lib/types"

const STARTERS = [
  "Coorg, 4–6 Nov, ₹4k a night, 2 guests",
  "Udaipur for our anniversary, mid-Dec, 5-star, lake view",
  "Goa weekend, Dec 14–16, beachfront, budget ₹7k",
]

export default function HomePage() {
  const {
    session,
    liveCalls,
    updateStage,
    setPreferences,
    setHotels,
    setApprovedHotels,
    setReport,
    upsertLiveCall,
  } = useSession()

  const handleWSEvent = useCallback(
    (event: WSEvent) => {
      switch (event.event) {
        case "stage_change":
          updateStage(event.stage)
          break
        case "hotels_found":
          if (event.hotels) setHotels(event.hotels)
          break
        case "call_started":
          upsertLiveCall(event.hotel, { status: "ringing" })
          break
        case "call_update":
          upsertLiveCall(event.hotel, {
            status: (event.status as CallStatus) ?? "connected",
            duration: event.duration,
          })
          break
        case "call_completed":
          upsertLiveCall(event.hotel, {
            status: "completed",
            price: event.price,
            available: event.available,
          })
          break
        case "report_ready":
          if (event.report) {
            setReport(event.report)
            updateStage("done")
          }
          break
      }
    },
    [updateStage, setHotels, upsertLiveCall, setReport]
  )

  const { isConnected } = useWebSocket({
    sessionId: session.session_id,
    enabled: session.session_id !== "pending",
    onEvent: handleWSEvent,
  })

  const { messages, isLoading, sendMessage } = useChat({
    sessionId: session.session_id,
    onStage: (stage) => updateStage(stage as Stage),
    onHotels: (hotels) => {
      if (hotels) setHotels(hotels)
    },
    onReport: (report) => {
      setReport(report)
      if (report.preferences) setPreferences(report.preferences)
    },
  })

  // Voice-mode toggle — defaults ON at the start of a session so onboarding
  // feels like a concierge call. User can bail to text with "Type instead".
  const [voiceMode, setVoiceMode] = useState(true)
  useEffect(() => {
    if (session.stage !== "collecting") setVoiceMode(false)
  }, [session.stage])

  const handleApproveHotels = useCallback(
    (hotels: Hotel[]) => {
      setApprovedHotels(hotels)
      updateStage("calling")
      // Send place_ids so backend can match exactly (no fuzzy parsing)
      const ids = hotels.map((h) => h.place_id).join(",")
      sendMessage(`APPROVE_IDS:${ids}`)
    },
    [setApprovedHotels, updateStage, sendMessage]
  )

  // Demo mode: hotels come in with phones already swapped. One or many —
  // backend parser accepts `pid=phone,pid=phone,...`.
  const handleDemoCall = useCallback(
    (hotels: Hotel[]) => {
      if (hotels.length === 0) return
      setApprovedHotels(hotels)
      updateStage("calling")
      const payload = hotels
        .map((h) => `${h.place_id}=${h.phone}`)
        .join(",")
      sendMessage(`DEMO_CALL:${payload}`)
    },
    [setApprovedHotels, updateStage, sendMessage]
  )

  const callProgress = useMemo(() => {
    const total = liveCalls.length
    const done = liveCalls.filter(
      (c) =>
        c.status === "completed" ||
        c.status === "no_answer" ||
        c.status === "failed"
    ).length
    return { done, total }
  }, [liveCalls])

  const savingsPercent = session.report?.average_savings_percent ?? null
  const stage = session.stage

  const mainPanel = (() => {
    if (stage === "calling") {
      return (
        <CallTracker
          calls={liveCalls}
          destination={session.preferences?.destination}
        />
      )
    }
    if (stage === "compiling") {
      return <CompilingView />
    }
    if (stage === "collecting" && voiceMode) {
      return (
        <VoiceOnboarding
          active={stage === "collecting" && voiceMode}
          onSend={sendMessage}
          onExit={() => setVoiceMode(false)}
        />
      )
    }
    return (
      <ChatPanel
        messages={messages}
        onSend={sendMessage}
        onApproveHotels={handleApproveHotels}
        onDemoCall={handleDemoCall}
        isLoading={isLoading}
        starters={STARTERS}
        placeholder={
          stage === "done"
            ? "Ask me anything about the report…"
            : "Where are we going? (e.g., Coorg, 4–6 Nov, ₹4k/night)"
        }
      />
    )
  })()

  return (
    <div className="relative isolate flex h-screen w-full">
      <TopBar stage={stage} />

      <div className="w-[320px] shrink-0 pt-14">
        <PipelineView
          currentStage={stage}
          preferences={session.preferences}
          hotelCount={session.hotels.length}
          callProgress={callProgress}
          savingsPercent={savingsPercent}
          sessionId={session.session_id}
          isConnected={isConnected}
        />
      </div>

      <main className="relative flex-1 overflow-hidden pt-14">
        <div className="h-full overflow-hidden">{mainPanel}</div>
      </main>
    </div>
  )
}

function TopBar({ stage }: { stage: Stage }) {
  return (
    <header className="absolute inset-x-0 top-0 z-20 flex h-14 items-center justify-between border-b border-hairline bg-canvas/80 px-7 backdrop-blur">
      <div className="flex items-center gap-3">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          className="text-cognac"
          aria-hidden
        >
          <path
            d="M12 2.5 L20 20 L12 15.5 L4 20 Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
        <span className="num text-[11px] tracking-[0.3em] text-ink">
          VOYAGEUR
        </span>
        <span className="h-3 w-px bg-hairline" />
        <span className="font-display italic text-[13px] text-ink-soft">
          an AI travel concierge
        </span>
      </div>

      <div className="hidden items-center gap-3 md:flex">
        <span className="eyebrow">Now</span>
        <span className="font-display italic text-[14px] text-cognac">
          {stageCopy(stage)}
        </span>
      </div>

      <div className="flex items-center gap-4 text-[11px]">
        <a className="eyebrow hover:text-ink transition-colors" href="#">
          Docs
        </a>
        <span className="h-3 w-px bg-hairline" />
        <button
          type="button"
          className="flex items-center gap-2 rounded-full border border-hairline bg-paper px-2.5 py-1.5 text-ink hover:border-ink/40"
        >
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-ink text-paper num text-[9px]">
            DK
          </span>
          <span className="text-[11.5px]">Divyansh</span>
        </button>
      </div>
    </header>
  )
}

function stageCopy(stage: Stage): string {
  switch (stage) {
    case "collecting":
      return "Listening…"
    case "researching":
      return "Scouting hotels…"
    case "approving":
      return "Your shortlist"
    case "calling":
      return "On the phone"
    case "compiling":
      return "Writing the report"
    case "done":
      return "Report ready"
  }
}
