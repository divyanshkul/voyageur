"use client"

import { Check, Phone, PhoneMissed, RotateCw, X } from "lucide-react"
import type { CallStatus as CallStatusT } from "@/lib/types"
import { inr, formatDuration, maskPhone } from "@/lib/format"
import { cn } from "@/lib/utils"

interface CallStatusProps {
  hotelName: string
  phone?: string
  status: CallStatusT
  duration: number
  price: number | null
  available: boolean | null
  index?: number
}

const STATUS_COPY: Record<CallStatusT, string> = {
  queued: "Queued",
  ringing: "Ringing",
  connected: "Connected",
  completed: "Completed",
  no_answer: "No answer",
  failed: "Failed",
  retrying: "Retrying",
}

function statusTone(s: CallStatusT): {
  ring: string
  text: string
  bg: string
  badge: string
} {
  switch (s) {
    case "ringing":
      return {
        ring: "border-saffron",
        text: "text-saffron",
        bg: "bg-[oklch(0.95_0.06_75/0.45)]",
        badge: "bg-saffron text-ink",
      }
    case "connected":
      return {
        ring: "border-sage",
        text: "text-sage",
        bg: "bg-sage-soft",
        badge: "bg-sage text-paper",
      }
    case "completed":
      return {
        ring: "border-sage/70",
        text: "text-sage",
        bg: "bg-sage-soft/60",
        badge: "bg-sage text-paper",
      }
    case "no_answer":
    case "failed":
      return {
        ring: "border-clay/60",
        text: "text-clay",
        bg: "bg-[oklch(0.95_0.05_30/0.4)]",
        badge: "bg-clay text-paper",
      }
    case "retrying":
      return {
        ring: "border-saffron",
        text: "text-saffron",
        bg: "bg-[oklch(0.95_0.06_75/0.35)]",
        badge: "bg-saffron text-ink",
      }
    case "queued":
    default:
      return {
        ring: "border-hairline",
        text: "text-ink-soft",
        bg: "bg-canvas",
        badge: "bg-canvas text-ink-soft",
      }
  }
}

export function CallStatus({
  hotelName,
  phone,
  status,
  duration,
  price,
  available,
  index,
}: CallStatusProps) {
  const tone = statusTone(status)
  const isLive = status === "ringing" || status === "connected" || status === "retrying"
  const isDone = status === "completed"
  const isFail = status === "no_answer" || status === "failed"

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-[14px] border bg-paper transition-all duration-500",
        "flex items-stretch gap-5 px-5 py-4",
        tone.ring,
        isLive && "shadow-[0_10px_36px_-22px_oklch(0.52_0.14_45/0.35)]"
      )}
    >
      {/* Live shimmer bar for active calls */}
      {isLive && (
        <div className="absolute inset-x-0 top-0 h-0.5 overflow-hidden">
          <div className="h-full w-1/3 bg-gradient-to-r from-transparent via-cognac to-transparent voy-shimmer" />
        </div>
      )}

      {/* Icon / phone visualization */}
      <div className="flex flex-col items-center pt-0.5">
        <div
          className={cn(
            "relative flex h-11 w-11 items-center justify-center rounded-full border-2",
            tone.ring,
            tone.bg
          )}
        >
          {isDone ? (
            <Check className={cn("h-4 w-4", tone.text)} strokeWidth={2.5} />
          ) : isFail ? (
            status === "no_answer" ? (
              <PhoneMissed
                className={cn("h-4 w-4", tone.text)}
                strokeWidth={2}
              />
            ) : (
              <X className={cn("h-4 w-4", tone.text)} strokeWidth={2.5} />
            )
          ) : status === "retrying" ? (
            <RotateCw
              className={cn("h-4 w-4 animate-spin", tone.text)}
              strokeWidth={2}
            />
          ) : status === "queued" ? (
            <span className="num text-[10px] text-ink-soft">
              {String((index ?? 0) + 1).padStart(2, "0")}
            </span>
          ) : (
            <Phone
              className={cn(
                "h-4 w-4",
                tone.text,
                status === "ringing" && "voy-dot-pulse"
              )}
              strokeWidth={2}
            />
          )}

          {/* Live pulsing ring for active calls */}
          {(status === "ringing" || status === "connected") && (
            <span
              className={cn(
                "absolute inset-0 rounded-full border-2",
                tone.ring,
                "opacity-0 animate-[voy-ring-soft_1.8s_ease-out_infinite]"
              )}
            />
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col gap-1">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h4 className="font-display text-[17px] leading-tight tracking-tight text-ink">
              {hotelName}
            </h4>
            {phone && (
              <div className="mt-0.5 num text-[11px] tracking-[0.1em] text-ink-soft">
                {maskPhone(phone)}
              </div>
            )}
          </div>
          <span
            className={cn(
              "rounded-full px-2.5 py-0.5 text-[10px] tracking-[0.14em] uppercase font-medium",
              tone.badge
            )}
          >
            {STATUS_COPY[status]}
          </span>
        </div>

        {/* Dynamic footer */}
        <div className="mt-1 flex items-center gap-5 text-[12px]">
          {(isLive || isDone) && (
            <div className="flex items-center gap-1.5">
              <span className="eyebrow text-[9.5px]">duration</span>
              <span className="num text-ink">{formatDuration(duration)}</span>
            </div>
          )}
          {(isDone || price != null) && (
            <div className="flex items-center gap-1.5">
              <span className="eyebrow text-[9.5px]">direct</span>
              <span
                className={cn(
                  "num font-medium",
                  price != null ? "text-ink" : "text-ink-soft"
                )}
              >
                {inr(price)}
              </span>
            </div>
          )}
          {isDone && available != null && (
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  available ? "bg-sage" : "bg-clay"
                )}
              />
              <span className="text-[11px] text-ink-soft">
                {available ? "rooms available" : "sold out"}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
