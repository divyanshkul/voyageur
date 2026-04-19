"use client"

import { useEffect, useRef, useState } from "react"
import { ArrowUp, Sparkles } from "lucide-react"
import type { ChatMessage as ChatMessageT, Hotel } from "@/lib/types"
import { ChatMessage, TypingIndicator } from "./ChatMessage"
import { HotelGrid } from "@/components/hotels/HotelGrid"
import { ReportView } from "@/components/report/ReportView"
import { cn } from "@/lib/utils"

interface ChatPanelProps {
  messages: ChatMessageT[]
  onSend: (text: string) => void
  onApproveHotels?: (hotels: Hotel[]) => void
  onDemoCall?: (hotel: Hotel) => void
  isLoading: boolean
  placeholder?: string
  starters?: string[]
}

export function ChatPanel({
  messages,
  onSend,
  onApproveHotels,
  onDemoCall,
  isLoading,
  placeholder = "Where are we going? (e.g., Coorg, 4–6 Nov, ₹4k/night)",
  starters,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages, isLoading])

  const handleSend = (text?: string) => {
    const msg = (text ?? draft).trim()
    if (!msg || isLoading) return
    onSend(msg)
    if (!text) setDraft("")
  }

  const showStarters = starters && starters.length > 0 && messages.length <= 1

  return (
    <div className="relative flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-hairline px-10 py-5">
        <div className="flex items-center gap-3">
          <span className="eyebrow">Conversation</span>
          <span className="h-3 w-px bg-hairline" />
          <span className="text-[12.5px] text-ink-soft">
            Tell me your plans — I'll handle the calls.
          </span>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-hairline bg-paper px-2.5 py-1 text-[10px] tracking-[0.18em] uppercase text-ink-soft">
          <Sparkles className="h-3 w-3 text-cognac" strokeWidth={1.75} />
          <span>Beta · Bengaluru</span>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="voy-scroll flex-1 overflow-y-auto px-10 pt-8"
      >
        <div className="mx-auto flex max-w-[760px] flex-col gap-7 pb-10">
          {messages.map((m) => (
            <div key={m.id} className="flex flex-col gap-5">
              <ChatMessage message={m} />
              {m.hotels && m.hotels.length > 0 && (
                <div className="pl-0 voy-rise">
                  <HotelGrid
                    hotels={m.hotels}
                    onApprove={(ids) => {
                      const approved = m.hotels!.filter((h) =>
                        ids.includes(h.place_id)
                      )
                      onApproveHotels?.(approved)
                    }}
                    onDemoCall={onDemoCall}
                  />
                </div>
              )}
              {m.report && (
                <div className="voy-rise">
                  <ReportView report={m.report} />
                </div>
              )}
            </div>
          ))}

          {isLoading && <TypingIndicator />}
          <div ref={endRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="border-t border-hairline bg-paper/80 px-10 py-5 backdrop-blur">
        <div className="mx-auto max-w-[760px]">
          {showStarters && (
            <div className="mb-3 flex flex-wrap gap-2">
              {starters!.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => handleSend(s)}
                  className="group rounded-full border border-hairline bg-canvas px-3.5 py-1.5 text-[12.5px] text-ink-soft transition-all hover:border-cognac hover:text-ink hover:shadow-[0_4px_14px_-10px_oklch(0.52_0.14_45/0.6)]"
                >
                  <span className="font-display italic text-cognac mr-1.5">
                    try:
                  </span>
                  {s}
                </button>
              ))}
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSend()
            }}
            className={cn(
              "group flex items-end gap-2 rounded-2xl border border-hairline bg-paper py-2 pl-4 pr-2 transition-all",
              "focus-within:border-ink/30 focus-within:shadow-[0_10px_40px_-22px_oklch(0.2_0.02_60/0.45)]"
            )}
          >
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder={placeholder}
              rows={1}
              className="flex-1 resize-none bg-transparent py-2 text-[15px] leading-snug text-ink outline-none placeholder:text-ink-soft/60"
              style={{ minHeight: "36px", maxHeight: "160px" }}
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!draft.trim() || isLoading}
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-full transition-all",
                "bg-ink text-paper hover:bg-cognac",
                "disabled:cursor-not-allowed disabled:bg-hairline disabled:text-ink-soft/50"
              )}
              aria-label="Send message"
            >
              <ArrowUp className="h-4 w-4" strokeWidth={2.2} />
            </button>
          </form>
          <div className="mt-2 flex items-center justify-between text-[10.5px] tracking-[0.14em] uppercase text-ink-soft/60">
            <span>
              <span className="num">↵</span> to send ·{" "}
              <span className="num">⇧↵</span> for a new line
            </span>
            <span className="num">Voyageur · claude · opus</span>
          </div>
        </div>
      </div>
    </div>
  )
}
