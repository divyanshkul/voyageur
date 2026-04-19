"use client"

import { PhoneOutgoing } from "lucide-react"
import { CallStatus } from "./CallStatus"
import type { LiveCall } from "@/lib/types"

interface CallTrackerProps {
  calls: LiveCall[]
  destination?: string
}

export function CallTracker({ calls, destination }: CallTrackerProps) {
  const total = calls.length
  const done = calls.filter(
    (c) =>
      c.status === "completed" ||
      c.status === "no_answer" ||
      c.status === "failed"
  ).length
  const inProgress = calls.filter(
    (c) =>
      c.status === "ringing" ||
      c.status === "connected" ||
      c.status === "retrying"
  ).length
  const queued = calls.filter((c) => c.status === "queued").length

  const pct = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <div className="flex h-full flex-col gap-6 overflow-hidden px-10 py-8">
      {/* Headline */}
      <div className="flex items-end justify-between gap-6">
        <div>
          <div className="eyebrow flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full rounded-full bg-cognac opacity-60 voy-dot-pulse" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-cognac" />
            </span>
            Live — Stage 03
          </div>
          <h2 className="mt-2 font-display text-[42px] leading-[1.02] tracking-tight text-ink">
            Dialing the <em className="display-italic text-cognac">front desks</em>
            {destination && (
              <span className="text-ink-soft"> in {destination}</span>
            )}
          </h2>
          <p className="mt-2 max-w-xl text-[13.5px] leading-relaxed text-ink-soft">
            Each hotel gets a real phone call. I&apos;ll ask for the best direct rate,
            check availability, and write down the details as they come in.
          </p>
        </div>

        <div className="flex items-center gap-8 rounded-2xl border border-hairline bg-paper px-6 py-4 paper">
          <Metric label="Complete" value={`${done}`} total={total} tone="sage" />
          <Divider />
          <Metric label="Live" value={`${inProgress}`} tone="cognac" />
          <Divider />
          <Metric label="Queued" value={`${queued}`} tone="muted" />
        </div>
      </div>

      {/* Progress bar */}
      <div className="relative">
        <div className="flex items-center gap-3">
          <span className="num text-[11px] tracking-[0.18em] uppercase text-ink-soft">
            Progress
          </span>
          <span className="num text-[11px] tracking-[0.18em] uppercase text-ink">
            {pct}%
          </span>
          <div className="h-px flex-1 bg-hairline" />
          <span className="num text-[11px] tracking-[0.18em] uppercase text-ink-soft">
            {done}/{total}
          </span>
        </div>
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-hairline">
          <div
            className="relative h-full bg-gradient-to-r from-cognac to-sage transition-all duration-700"
            style={{ width: `${pct}%` }}
          >
            {inProgress > 0 && (
              <div className="absolute inset-0 voy-shimmer" />
            )}
          </div>
        </div>
      </div>

      {/* Call cards list */}
      <div className="voy-scroll flex flex-1 flex-col gap-3 overflow-y-auto pr-2">
        {calls.length === 0 ? (
          <EmptyCalls />
        ) : (
          calls.map((c, i) => (
            <CallStatus
              key={`${c.hotel_name}-${i}`}
              hotelName={c.hotel_name}
              phone={c.phone}
              status={c.status}
              duration={c.duration}
              price={c.price}
              available={c.available}
              index={i}
            />
          ))
        )}
      </div>
    </div>
  )
}

function Metric({
  label,
  value,
  total,
  tone,
}: {
  label: string
  value: string
  total?: number
  tone: "sage" | "cognac" | "muted"
}) {
  const color =
    tone === "sage" ? "text-sage" : tone === "cognac" ? "text-cognac" : "text-ink"
  return (
    <div className="flex flex-col items-center">
      <div className={`num text-[28px] leading-none ${color}`}>
        {value}
        {total != null && (
          <span className="text-ink-soft text-[14px]">/{total}</span>
        )}
      </div>
      <div className="eyebrow mt-1 text-[9.5px]">{label}</div>
    </div>
  )
}

function Divider() {
  return <div className="h-10 w-px bg-hairline" />
}

function EmptyCalls() {
  return (
    <div className="flex flex-1 items-center justify-center rounded-2xl border border-dashed border-hairline p-10 text-center">
      <div className="flex flex-col items-center gap-3">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-paper">
          <PhoneOutgoing
            className="h-5 w-5 text-ink-soft/60"
            strokeWidth={1.5}
          />
        </div>
        <p className="font-display italic text-ink-soft text-[15px]">
          preparing the phone lines…
        </p>
      </div>
    </div>
  )
}
