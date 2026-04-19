"use client"

import type { LucideIcon } from "lucide-react"
import { CheckCircle2, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

export type StepStatus = "pending" | "active" | "done"

interface PipelineStepProps {
  index: number
  icon: LucideIcon
  name: string
  status: StepStatus
  subtitle: string | null
  isLast?: boolean
}

export function PipelineStep({
  index,
  icon: Icon,
  name,
  status,
  subtitle,
  isLast = false,
}: PipelineStepProps) {
  const isActive = status === "active"
  const isDone = status === "done"

  return (
    <div className="relative flex gap-4">
      {/* Icon column */}
      <div className="relative flex flex-col items-center">
        <div
          className={cn(
            "relative flex h-11 w-11 items-center justify-center rounded-full border transition-all duration-500",
            isDone &&
              "border-sage/70 bg-sage-soft text-sage shadow-[0_0_0_4px_oklch(0.94_0.03_140/0.55)]",
            isActive &&
              "border-cognac bg-paper text-cognac voy-ring shadow-[0_0_0_4px_oklch(0.92_0.04_58/0.8)]",
            status === "pending" &&
              "border-hairline bg-paper text-ink-soft/60"
          )}
        >
          {isDone ? (
            <CheckCircle2 className="h-5 w-5" strokeWidth={1.75} />
          ) : isActive ? (
            <Loader2
              className="h-5 w-5 animate-spin"
              strokeWidth={1.75}
            />
          ) : (
            <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />
          )}
        </div>

        {/* Connector line */}
        {!isLast && (
          <div className="relative flex-1 w-px my-2 min-h-[36px]">
            <div className="absolute inset-0 bg-hairline" />
            <div
              className={cn(
                "absolute inset-0 bg-gradient-to-b from-cognac to-sage transition-transform duration-700 origin-top",
                isDone ? "scale-y-100" : "scale-y-0"
              )}
            />
          </div>
        )}
      </div>

      {/* Text column */}
      <div className="flex-1 pb-8">
        <div className="flex items-baseline gap-2">
          <span className="num text-[10px] tracking-[0.22em] text-ink-soft/70">
            {String(index + 1).padStart(2, "0")}
          </span>
          <h3
            className={cn(
              "font-display text-[17px] tracking-tight leading-none",
              isDone && "text-ink",
              isActive && "text-ink",
              status === "pending" && "text-ink-soft/70"
            )}
          >
            {name}
          </h3>
        </div>
        <div className="mt-1.5 text-[12.5px] leading-snug text-ink-soft min-h-[1.2em]">
          {subtitle ? (
            <span className="voy-fade">{subtitle}</span>
          ) : (
            <span className="text-ink-soft/40">
              {isActive ? "in progress…" : "awaiting"}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
