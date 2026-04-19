"use client"

import { Sparkles, Star } from "lucide-react"
import type { HotelComparison } from "@/lib/types"
import { inr } from "@/lib/format"
import { cn } from "@/lib/utils"
import { SavingsBadge } from "./SavingsBadge"

interface ComparisonTableProps {
  comparisons: HotelComparison[]
  topPickId?: string | null
}

export function ComparisonTable({
  comparisons,
  topPickId,
}: ComparisonTableProps) {
  const sorted = [...comparisons].sort((a, b) => {
    const av = a.savings_percent ?? -Infinity
    const bv = b.savings_percent ?? -Infinity
    return bv - av
  })

  return (
    <div className="overflow-hidden rounded-2xl border border-hairline bg-paper">
      {/* Header */}
      <div className="grid grid-cols-[1.6fr_0.7fr_0.8fr_0.8fr_0.9fr] gap-4 border-b border-hairline bg-canvas/70 px-5 py-3 text-[10px] tracking-[0.18em] uppercase text-ink-soft">
        <div>Hotel</div>
        <div className="text-right">Rating</div>
        <div className="text-right">OTA</div>
        <div className="text-right">Direct</div>
        <div className="text-right">You Save</div>
      </div>

      {/* Rows */}
      <div>
        {sorted.map((cmp, i) => {
          const isTop = topPickId
            ? cmp.hotel.place_id === topPickId
            : i === 0 && (cmp.savings_percent ?? 0) > 0
          return (
            <div
              key={cmp.hotel.place_id}
              className={cn(
                "grid grid-cols-[1.6fr_0.7fr_0.8fr_0.8fr_0.9fr] gap-4 border-b border-hairline px-5 py-4 text-[13.5px] transition-colors last:border-b-0",
                isTop
                  ? "bg-cognac-soft/60"
                  : "hover:bg-canvas/50"
              )}
            >
              {/* Hotel */}
              <div className="flex min-w-0 items-center gap-3">
                {isTop && (
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cognac text-paper">
                    <Sparkles className="h-3 w-3" strokeWidth={2} />
                  </div>
                )}
                <div className="min-w-0">
                  <div className="font-display text-[15px] leading-tight tracking-tight text-ink truncate">
                    {cmp.hotel.name}
                  </div>
                  {isTop && (
                    <div className="eyebrow text-[9.5px] text-cognac mt-0.5">
                      Best deal
                    </div>
                  )}
                </div>
              </div>

              {/* Rating */}
              <div className="flex items-center justify-end gap-1 text-ink-soft">
                <Star className="h-3 w-3 fill-saffron text-saffron" strokeWidth={1} />
                <span className="num text-ink">{cmp.hotel.rating.toFixed(1)}</span>
              </div>

              {/* OTA */}
              <div className="text-right num text-ink-soft">
                {inr(cmp.ota_price)}
              </div>

              {/* Direct */}
              <div className="text-right num text-ink font-medium">
                {inr(cmp.direct_price)}
              </div>

              {/* Savings */}
              <div className="flex justify-end">
                <SavingsBadge percent={cmp.savings_percent} size="sm" />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
