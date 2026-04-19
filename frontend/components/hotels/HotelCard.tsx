"use client"

import { Check, MapPin, Star } from "lucide-react"
import type { Hotel } from "@/lib/types"
import { inr } from "@/lib/format"
import { cn } from "@/lib/utils"

interface HotelCardProps {
  hotel: Hotel
  selected: boolean
  onToggle: () => void
}

export function HotelCard({ hotel, selected, onToggle }: HotelCardProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        "group relative flex w-full flex-col gap-3 overflow-hidden rounded-[14px] border bg-paper p-4 text-left transition-all",
        "hover:-translate-y-0.5",
        selected
          ? "border-cognac shadow-[0_18px_40px_-24px_oklch(0.52_0.14_45/0.55)]"
          : "border-hairline hover:border-ink/25 hover:shadow-[0_14px_32px_-24px_oklch(0.2_0.02_60/0.35)]"
      )}
    >
      {/* Selection corner */}
      <div
        className={cn(
          "absolute right-3 top-3 flex h-6 w-6 items-center justify-center rounded-full border transition-all",
          selected
            ? "border-cognac bg-cognac text-paper"
            : "border-hairline bg-paper text-ink-soft/40 group-hover:border-ink/40"
        )}
      >
        {selected && <Check className="h-3.5 w-3.5" strokeWidth={2.5} />}
      </div>

      {/* Match score band */}
      {hotel.match_score != null && (
        <div className="absolute left-0 top-0 h-full w-0.5 bg-gradient-to-b from-cognac via-saffron to-sage" />
      )}

      <div className="flex items-start justify-between pr-8">
        <div className="flex-1">
          <h4 className="font-display text-[18px] leading-[1.1] tracking-tight text-ink">
            {hotel.name}
          </h4>
          <div className="mt-1 flex items-center gap-1.5 text-[12px] text-ink-soft">
            <MapPin className="h-3 w-3" strokeWidth={1.5} />
            <span className="truncate max-w-[220px]">{hotel.address}</span>
          </div>
        </div>
      </div>

      {/* Rating + match + price row */}
      <div className="flex items-center gap-3 text-[12px]">
        <div className="flex items-center gap-1 rounded-full bg-canvas px-2 py-1">
          <Star
            className="h-3 w-3 fill-saffron text-saffron"
            strokeWidth={1}
          />
          <span className="num font-medium text-ink">
            {hotel.rating.toFixed(1)}
          </span>
        </div>
        {hotel.match_score != null && (
          <div className="flex items-center gap-1.5">
            <span className="eyebrow text-[9.5px]">match</span>
            <span className="num text-cognac font-medium">
              {Math.round(hotel.match_score * 100)}
            </span>
          </div>
        )}
        <div className="ml-auto flex flex-col items-end">
          <span className="eyebrow text-[9.5px]">OTA</span>
          <span className="num text-ink leading-none">
            {inr(hotel.ota_price)}
            <span className="text-ink-soft text-[10px] ml-0.5">/night</span>
          </span>
        </div>
      </div>

      {/* Amenities */}
      {hotel.amenities.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {hotel.amenities.slice(0, 5).map((a) => (
            <span
              key={a}
              className="rounded-full border border-hairline px-2 py-0.5 text-[10.5px] text-ink-soft"
            >
              {a}
            </span>
          ))}
          {hotel.amenities.length > 5 && (
            <span className="text-[10.5px] text-ink-soft/60 self-center">
              +{hotel.amenities.length - 5}
            </span>
          )}
        </div>
      )}
    </button>
  )
}
