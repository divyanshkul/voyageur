"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { Phone, X } from "lucide-react"
import { HotelCard } from "./HotelCard"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { Hotel } from "@/lib/types"

interface HotelGridProps {
  hotels: Hotel[]
  onApprove: (selectedIds: string[]) => void
  onDemoCall?: (hotels: Hotel[]) => void
}

const INDIAN_MOBILE_REGEX = /^[6-9]\d{9}$/

export function HotelGrid({ hotels, onApprove, onDemoCall }: HotelGridProps) {
  const initial = useMemo(() => new Set(hotels.map((h) => h.place_id)), [hotels])
  const [selected, setSelected] = useState<Set<string>>(initial)
  const [demoOpen, setDemoOpen] = useState(false)
  const [demoPhones, setDemoPhones] = useState<Record<string, string>>({})
  const [demoErrors, setDemoErrors] = useState<Record<string, string>>({})
  const firstInputRef = useRef<HTMLInputElement>(null)

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

  const modalHotels = useMemo(() => {
    const picked = hotels.filter((h) => selected.has(h.place_id))
    if (picked.length > 0) return picked
    return hotels.length > 0 ? [hotels[0]] : []
  }, [hotels, selected])

  const allValid =
    modalHotels.length > 0 &&
    modalHotels.every((h) => INDIAN_MOBILE_REGEX.test(demoPhones[h.place_id] ?? ""))

  const openDemoModal = () => {
    setDemoPhones({})
    setDemoErrors({})
    setDemoOpen(true)
  }

  const closeDemoModal = () => {
    setDemoOpen(false)
    setDemoErrors({})
  }

  const submitDemoCall = () => {
    if (!onDemoCall || modalHotels.length === 0) return
    const nextErrors: Record<string, string> = {}
    for (const h of modalHotels) {
      const digits = (demoPhones[h.place_id] ?? "").replace(/\D/g, "")
      if (!INDIAN_MOBILE_REGEX.test(digits)) {
        nextErrors[h.place_id] = "Enter a 10-digit Indian mobile number."
      }
    }
    if (Object.keys(nextErrors).length > 0) {
      setDemoErrors(nextErrors)
      return
    }
    const hotelsWithPhones = modalHotels.map((h) => ({
      ...h,
      phone: `+91${demoPhones[h.place_id]}`,
    }))
    onDemoCall(hotelsWithPhones)
    closeDemoModal()
  }

  useEffect(() => {
    if (!demoOpen) return
    const t = setTimeout(() => firstInputRef.current?.focus(), 0)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeDemoModal()
    }
    window.addEventListener("keydown", onKey)
    return () => {
      clearTimeout(t)
      window.removeEventListener("keydown", onKey)
    }
  }, [demoOpen])

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
              onClick={openDemoModal}
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

      {demoOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="demo-call-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-sm p-4"
          onClick={closeDemoModal}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-sm rounded-2xl border border-hairline bg-paper p-5 shadow-xl max-h-[85vh] overflow-y-auto"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="eyebrow">Demo call</div>
                <h3
                  id="demo-call-title"
                  className="mt-1 font-display text-[20px] leading-tight tracking-tight text-ink"
                >
                  {modalHotels.length > 1 ? (
                    <>
                      Which numbers should we{" "}
                      <span className="italic text-ink-soft">ring?</span>
                    </>
                  ) : (
                    <>
                      Which number should we{" "}
                      <span className="italic text-ink-soft">ring?</span>
                    </>
                  )}
                </h3>
              </div>
              <button
                type="button"
                onClick={closeDemoModal}
                aria-label="Close"
                className="text-ink-soft hover:text-ink"
              >
                <X className="h-4 w-4" strokeWidth={2} />
              </button>
            </div>

            <div className="mt-4 flex flex-col gap-4">
              {modalHotels.map((h, idx) => {
                const value = demoPhones[h.place_id] ?? ""
                const error = demoErrors[h.place_id]
                return (
                  <div key={h.place_id}>
                    <label className="block text-[12px] tracking-[0.08em] uppercase text-ink-soft truncate">
                      {h.name}
                    </label>
                    <div className="mt-1.5 flex items-stretch rounded-lg border border-input focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
                      <span className="flex items-center px-3 text-[14px] text-ink-soft border-r border-hairline select-none">
                        +91
                      </span>
                      <Input
                        ref={idx === 0 ? firstInputRef : undefined}
                        type="tel"
                        inputMode="numeric"
                        autoComplete="tel-national"
                        maxLength={10}
                        value={value}
                        placeholder="9876543210"
                        onChange={(e) => {
                          const next = e.target.value.replace(/\D/g, "").slice(0, 10)
                          setDemoPhones((prev) => ({ ...prev, [h.place_id]: next }))
                          if (error) {
                            setDemoErrors((prev) => {
                              const { [h.place_id]: _drop, ...rest } = prev
                              return rest
                            })
                          }
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault()
                            submitDemoCall()
                          }
                        }}
                        className="border-0 rounded-l-none focus-visible:ring-0 focus-visible:border-0"
                      />
                    </div>
                    {error && (
                      <p className="mt-1.5 text-[12px] text-destructive">{error}</p>
                    )}
                  </div>
                )
              })}
            </div>

            <p className="mt-3 text-[12px] text-ink-soft">
              10-digit number starting with 6, 7, 8, or 9.
            </p>

            <div className="mt-5 flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={closeDemoModal}
                className="rounded-full h-9 px-4 text-[13px]"
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={submitDemoCall}
                disabled={!allValid}
                className="rounded-full bg-cognac/90 text-paper hover:bg-cognac disabled:bg-hairline disabled:text-ink-soft/50 h-9 px-5 text-[13px]"
              >
                <Phone className="h-3.5 w-3.5" strokeWidth={2} />
                <span className="ml-1.5">
                  {modalHotels.length > 1
                    ? `Place ${modalHotels.length} calls`
                    : "Place call"}
                </span>
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
