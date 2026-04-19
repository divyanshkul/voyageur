"use client"

import {
  FileText,
  MessageSquare,
  Phone,
  Search,
} from "lucide-react"
import { PipelineStep, type StepStatus } from "./PipelineStep"
import type { Stage, TravelPreferences } from "@/lib/types"
import { nightCount, shortDate } from "@/lib/format"

interface PipelineViewProps {
  currentStage: Stage
  preferences: TravelPreferences | null
  hotelCount: number
  callProgress: { done: number; total: number }
  savingsPercent: number | null
  sessionId: string
  isConnected: boolean
}

const STAGE_STEP_INDEX: Record<Stage, number> = {
  collecting: 0,
  researching: 1,
  approving: 1,
  calling: 2,
  compiling: 3,
  done: 3,
}

function statusFor(stepIdx: number, stage: Stage): StepStatus {
  const active = STAGE_STEP_INDEX[stage]
  if (stage === "done") return "done"
  if (stepIdx < active) return "done"
  if (stepIdx === active) return "active"
  return "pending"
}

export function PipelineView({
  currentStage,
  preferences,
  hotelCount,
  callProgress,
  savingsPercent,
  sessionId,
  isConnected,
}: PipelineViewProps) {
  const prefSubtitle =
    preferences &&
    (() => {
      const nights = nightCount(preferences.check_in, preferences.check_out)
      return `${preferences.destination} · ${nights} night${nights === 1 ? "" : "s"}`
    })()

  const prefDates =
    preferences && preferences.check_in && preferences.check_out
      ? `${shortDate(preferences.check_in)} → ${shortDate(preferences.check_out)}`
      : null

  const researchSubtitle =
    hotelCount > 0 ? `Found ${hotelCount} hotel${hotelCount === 1 ? "" : "s"}` : null

  const callSubtitle =
    callProgress.total > 0
      ? `${callProgress.done}/${callProgress.total} call${
          callProgress.total === 1 ? "" : "s"
        }${currentStage === "calling" ? " · live" : ""}`
      : null

  const reportSubtitle =
    savingsPercent != null
      ? `Avg ${Math.abs(savingsPercent).toFixed(0)}% ${
          savingsPercent >= 0 ? "saved" : "over"
        }`
      : null

  const steps = [
    {
      icon: MessageSquare,
      name: "Preferences",
      subtitle: prefSubtitle ?? null,
      extra: prefDates,
    },
    {
      icon: Search,
      name: "Research",
      subtitle: researchSubtitle,
      extra: null,
    },
    {
      icon: Phone,
      name: "Calling",
      subtitle: callSubtitle,
      extra: null,
    },
    {
      icon: FileText,
      name: "Report",
      subtitle: reportSubtitle,
      extra: null,
    },
  ]

  return (
    <aside className="relative flex h-full flex-col gap-8 border-r border-hairline bg-paper/60 px-7 pt-7 pb-6">
      {/* Brand */}
      <div>
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <div className="h-2 w-2 rounded-full bg-cognac" />
            <div className="absolute inset-0 rounded-full bg-cognac voy-dot-pulse opacity-60" />
          </div>
          <span className="num text-[11px] tracking-[0.3em] text-ink">
            VOYAGEUR
          </span>
        </div>
        <p className="mt-3 font-display italic text-[22px] leading-[1.05] text-ink">
          The hotel concierge<br />
          <span className="text-ink-soft">that picks up the phone.</span>
        </p>
      </div>

      <div className="hairline-divider" />

      {/* Pipeline */}
      <div>
        <div className="eyebrow mb-5">Concierge Pipeline</div>
        <div className="flex flex-col">
          {steps.map((step, i) => (
            <PipelineStep
              key={step.name}
              index={i}
              icon={step.icon}
              name={step.name}
              status={statusFor(i, currentStage)}
              subtitle={step.subtitle ?? step.extra ?? null}
              isLast={i === steps.length - 1}
            />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="mt-auto">
        <div className="hairline-divider mb-4" />
        <div className="flex items-center justify-between text-[10.5px] tracking-[0.18em] uppercase text-ink-soft">
          <div className="flex items-center gap-2">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                isConnected ? "bg-sage voy-dot-pulse" : "bg-ink-soft/40"
              }`}
            />
            <span>{isConnected ? "Live" : "Idle"}</span>
          </div>
          <span className="num normal-case tracking-normal text-ink-soft/60 text-[10.5px]">
            {sessionId.slice(0, 8)}
          </span>
        </div>
      </div>
    </aside>
  )
}
