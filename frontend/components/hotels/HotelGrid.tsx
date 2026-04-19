"use client"

import { useMemo, useState } from "react"
import { Phone } from "lucide-react"
import { HotelCard } from "./HotelCard"
import { Button } from "@/components/ui/button"
import type { Hotel } from "@/lib/types"

interface HotelGridProps {
  hotels: Hotel[]
  onApprove: (selectedIds: string[]) => void
  onDemoCall?: (hotel: Hotel) => void
}

const DEMO_PHONE = "+919584009988"

export function HotelGrid({ hotels, onApprove, onDemoCall }: HotelGridProps) {
  const initial = useMemo(() => new Set(hotels.map((h) => h.place_id)), [hotels])
  const [selected, setSelected] = useState<Set<string>>(initial)

  const toggle = (id: string) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  const toggleAll = () => {
    if (selected.size === hotels.length) setSelected(new Set())
    else setSelected(new Set(hotels.map((h) => h.place_id)))
  }

  const selectedCount = selected.size

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-hairline bg-canvas/60 p-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="eyebrow">Shortlist</div>
          <h3 className="mt-1 font-display text-[22px] leading-none tracking-tight text-ink">
            <span className="num">{hotels.length}</span> hotels{" "}
            <span className="text-ink-soft italic">worth a call</span>
          </h3>
        </div>

        <div className="flex items-center gap-3">
          {onDemoCall && hotels.length > 0 && (
            <Button
              type="button"
              onClick={() => {
                const demoHotel = { ...hotels[0], phone: DEMO_PHONE }
                onDemoCall(demoHotel)
              }}
              className="rounded-full bg-cognac/90 text-paper hover:bg-cognac pl-4 pr-5 h-9"
            >
              <Phone className="h-3.5 w-3.5" strokeWidth={2} />
              <span className="ml-1.5 text-[13px]">Demo Call</span>
            </Button>
          )}
          <button
            type="button"
            onClick={toggleAll}
            className="text-[12px] text-ink-soft hover:text-ink underline underline-offset-4 decoration-hairline hover:decoration-cognac"
          >
            {selected.size === hotels.length ? "Clear all" : "Select all"}
          </button>
          <span className="num text-[11px] tracking-[0.14em] uppercase text-ink-soft">
            {selectedCount}/{hotels.length}
          </span>
          <Button
            type="button"
            onClick={() => onApprove(Array.from(selected))}
            disabled={selectedCount === 0}
            className="rounded-full bg-ink text-paper hover:bg-cognac disabled:bg-hairline disabled:text-ink-soft/50 pl-4 pr-5 h-9"
          >
            <Phone className="h-3.5 w-3.5" strokeWidth={2} />
            <span className="ml-1.5 text-[13px]">
              Call {selectedCount > 0 ? selectedCount : ""} selected
            </span>
          </Button>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {hotels.map((hotel) => (
          <HotelCard
            key={hotel.place_id}
            hotel={hotel}
            selected={selected.has(hotel.place_id)}
            onToggle={() => toggle(hotel.place_id)}
          />
        ))}
      </div>
    </div>
  )
}
