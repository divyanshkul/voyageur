"use client"

import { FileText } from "lucide-react"

const LINES = [
  "Reconciling OTA quotes with direct rates…",
  "Cross-checking availability and cancellation windows…",
  "Drafting the comparison ledger…",
  "Picking the best deal of the bunch…",
]

export function CompilingView() {
  return (
    <div className="flex h-full items-center justify-center px-10">
      <div className="relative w-full max-w-[520px] overflow-hidden rounded-[20px] border border-hairline bg-paper p-10 paper">
        <div className="absolute inset-x-0 top-0 h-[3px] overflow-hidden">
          <div className="h-full w-1/3 bg-gradient-to-r from-transparent via-cognac to-transparent voy-shimmer" />
        </div>

        <div className="flex items-center gap-4">
          <div className="relative flex h-14 w-14 items-center justify-center rounded-full border border-hairline bg-canvas">
            <FileText
              className="h-5 w-5 text-cognac"
              strokeWidth={1.5}
            />
            <span className="absolute inset-0 rounded-full border-2 border-cognac animate-[voy-ring-soft_1.8s_ease-out_infinite]" />
          </div>
          <div>
            <div className="eyebrow">Stage 04</div>
            <h2 className="mt-1 font-display text-[30px] leading-none tracking-tight text-ink">
              Writing it up…
            </h2>
          </div>
        </div>

        <ul className="mt-8 flex flex-col gap-3">
          {LINES.map((line, i) => (
            <li
              key={line}
              className="flex items-center gap-3 voy-rise"
              style={{ animationDelay: `${i * 180}ms` }}
            >
              <span className="relative flex h-1.5 w-1.5">
                <span
                  className="absolute inline-flex h-full w-full rounded-full bg-cognac opacity-50 voy-dot-pulse"
                  style={{ animationDelay: `${i * 180}ms` }}
                />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-cognac" />
              </span>
              <span className="text-[13.5px] text-ink-soft italic font-display">
                {line}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
