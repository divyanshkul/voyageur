"use client"

import { Keyboard, Mic, MicOff, X } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { VoiceOrb } from "./VoiceOrb"
import { useVoiceTurn } from "@/hooks/useVoiceTurn"
import { cn } from "@/lib/utils"

interface Turn {
  id: string
  role: "concierge" | "guest"
  text: string
}

interface VoiceOnboardingProps {
  /** Send a user-turn text to the backend; returns the agent's reply. */
  onSend: (text: string) => Promise<string>
  /** Called when the user wants to bail out to the text composer. */
  onExit: () => void
  /** Whether this overlay is still appropriate — externally controlled. */
  active: boolean
  /** Optional starter line the concierge speaks on first click. */
  greeting?: string
}

const DEFAULT_GREETING =
  "Bonjour, I'm Voyageur. Tell me where you're headed, when, and what you're looking for — I'll ring the hotels directly."

/**
 * Full-bleed voice-mode overlay. Covers the main panel (not the sidebar).
 * Uses Sarvam TTS for the concierge voice and Sarvam STT to transcribe
 * the guest's speech. Each turn is relayed to the existing /api/chat
 * pipeline via `onSend`, so the backend behavior is identical to the
 * text-mode chat.
 */
export function VoiceOnboarding({
  onSend,
  onExit,
  active,
  greeting = DEFAULT_GREETING,
}: VoiceOnboardingProps) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [started, setStarted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentPrompt, setCurrentPrompt] = useState<string>(greeting)
  const isRunningRef = useRef(false)

  const { state, level, speak, startListening, stopListening, cancel } =
    useVoiceTurn({
      onError: (e) => setError(e.message),
    })

  // Push a turn to the history
  const pushTurn = useCallback((role: Turn["role"], text: string) => {
    if (!text.trim()) return
    setTurns((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role, text: text.trim() },
    ])
  }, [])

  // --- Start the conversation (auto greeting → listen) ---
  const handleStart = useCallback(async () => {
    if (started || isRunningRef.current) return
    setStarted(true)
    isRunningRef.current = true
    setError(null)

    pushTurn("concierge", greeting)
    await speak(greeting)

    // After greeting, begin listening for the first guest turn.
    if (active) await startListening()
    isRunningRef.current = false
  }, [active, greeting, pushTurn, speak, startListening, started])

  // --- User tap to stop speaking → STT → backend → TTS reply → listen again ---
  const handleStop = useCallback(async () => {
    if (state !== "listening" || isRunningRef.current) return
    isRunningRef.current = true
    setError(null)

    const transcript = await stopListening()
    if (!transcript.trim()) {
      // Nothing captured — just go back to listening.
      isRunningRef.current = false
      if (active) await startListening()
      return
    }
    pushTurn("guest", transcript)

    let reply: string
    try {
      reply = await onSend(transcript)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "backend unreachable"
      setError(msg)
      isRunningRef.current = false
      return
    }

    if (!active) {
      // Stage moved on while we were thinking — exit gracefully.
      isRunningRef.current = false
      return
    }

    setCurrentPrompt(reply)
    pushTurn("concierge", reply)
    await speak(reply)

    // Loop: start listening again for next guest turn (only if still active).
    if (active) await startListening()
    isRunningRef.current = false
  }, [
    active,
    onSend,
    pushTurn,
    speak,
    startListening,
    state,
    stopListening,
  ])

  // When the parent flips `active` off (stage advanced), stop everything.
  useEffect(() => {
    if (!active) cancel()
  }, [active, cancel])

  // Status label under the orb
  const statusLabel = (() => {
    if (!started) return "Tap to begin"
    if (state === "speaking") return "Concierge speaking"
    if (state === "listening") return "Listening…"
    if (state === "thinking") return "Thinking…"
    return "Standing by"
  })()

  const canTapToStop = state === "listening"

  return (
    <div
      className={cn(
        "relative flex h-full w-full flex-col overflow-hidden",
        "bg-canvas"
      )}
    >
      {/* Ambient background wash */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(900px 520px at 50% 20%, oklch(0.93 0.05 55 / 0.6), transparent 60%), radial-gradient(700px 520px at 50% 110%, oklch(0.94 0.04 140 / 0.45), transparent 55%)",
        }}
      />

      {/* Top strip — mode badge + exit-to-text */}
      <div className="relative z-10 flex items-center justify-between border-b border-hairline/60 px-10 py-5">
        <div className="flex items-center gap-3">
          <span className="eyebrow">Voice mode</span>
          <span className="h-3 w-px bg-hairline" />
          <span className="text-[12.5px] text-ink-soft">
            <span className="font-display italic text-cognac">
              In conversation
            </span>{" "}
            — speak freely, tap the mic when you&apos;re done.
          </span>
        </div>
        <button
          type="button"
          onClick={onExit}
          className="group flex items-center gap-2 rounded-full border border-hairline bg-paper/80 px-3 py-1.5 text-[11px] tracking-[0.14em] uppercase text-ink-soft transition-all hover:border-ink/40 hover:text-ink"
        >
          <Keyboard className="h-3.5 w-3.5" strokeWidth={1.75} />
          <span>Type instead</span>
        </button>
      </div>

      {/* Main stage */}
      <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-10 pb-6 min-h-0">
        {/* Eyebrow line */}
        <div className="mb-3 flex items-center gap-3 text-ink-soft">
          <span className="h-px w-8 bg-hairline" />
          <span className="eyebrow">Your concierge</span>
          <span className="h-px w-8 bg-hairline" />
        </div>

        {/* The orb */}
        <VoiceOrb state={state} level={level} size={200} />

        {/* Status label */}
        <div className="mt-4 flex items-center gap-2.5 text-[11px] tracking-[0.3em] uppercase text-ink-soft">
          <span
            className={cn(
              "inline-block h-1.5 w-1.5 rounded-full",
              state === "listening" && "bg-cognac voy-dot-pulse",
              state === "speaking" && "bg-sage",
              state === "thinking" && "bg-saffron voy-dot-pulse",
              state === "idle" && "bg-hairline"
            )}
          />
          <span className="num">{statusLabel}</span>
        </div>

        {/* Current concierge line — editorial quote */}
        <div className="mt-5 max-w-[620px] text-center">
          <p className="font-display italic text-[20px] leading-[1.3] text-ink line-clamp-3">
            &ldquo;{currentPrompt}&rdquo;
          </p>
        </div>

        {/* Last guest turn — captured transcript */}
        {turns.filter((t) => t.role === "guest").slice(-1).map((t) => (
          <div
            key={t.id}
            className="mt-4 voy-rise max-w-[620px] rounded-2xl border border-hairline bg-paper/80 px-4 py-2 text-[13px] text-ink-soft backdrop-blur"
          >
            <span className="eyebrow mr-2 text-cognac">You said</span>
            <span className="italic line-clamp-2">&ldquo;{t.text}&rdquo;</span>
          </div>
        ))}

        {error && (
          <div className="mt-3 rounded-lg border border-clay/30 bg-clay/5 px-3 py-2 text-[12px] text-clay voy-rise">
            {error}
          </div>
        )}

        {/* Action button */}
        <div className="mt-6">
          {!started ? (
            <button
              type="button"
              onClick={handleStart}
              className={cn(
                "group relative flex items-center gap-3 rounded-full bg-ink px-6 py-3.5 text-paper",
                "text-[12.5px] tracking-[0.2em] uppercase num",
                "transition-all hover:bg-cognac"
              )}
            >
              <Mic className="h-4 w-4" strokeWidth={1.8} />
              <span>Begin the call</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleStop}
              disabled={!canTapToStop}
              className={cn(
                "group relative flex items-center gap-3 rounded-full px-6 py-3.5",
                "text-[12.5px] tracking-[0.2em] uppercase num transition-all",
                canTapToStop
                  ? "bg-cognac text-paper hover:bg-ink"
                  : "bg-paper text-ink-soft/60 border border-hairline cursor-not-allowed"
              )}
            >
              {canTapToStop ? (
                <>
                  <MicOff className="h-4 w-4" strokeWidth={1.8} />
                  <span>Tap when you&apos;re done</span>
                </>
              ) : (
                <>
                  <Mic className="h-4 w-4 opacity-60" strokeWidth={1.8} />
                  <span>
                    {state === "speaking" ? "Let me finish…" : "One moment…"}
                  </span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Bottom transcript ribbon — compact history scroller */}
      {turns.length > 2 && (
        <div className="relative z-10 border-t border-hairline/60 bg-paper/50 px-10 py-3 backdrop-blur">
          <div className="voy-scroll flex gap-2 overflow-x-auto">
            {turns.slice(0, -1).map((t) => (
              <div
                key={t.id}
                className={cn(
                  "flex shrink-0 items-center gap-2 rounded-full border px-3 py-1 text-[11px]",
                  t.role === "concierge"
                    ? "border-cognac/30 bg-cognac-soft/50 text-cognac"
                    : "border-hairline bg-canvas text-ink-soft"
                )}
              >
                <span className="eyebrow text-[9px]">
                  {t.role === "concierge" ? "V" : "You"}
                </span>
                <span className="max-w-[320px] truncate">{t.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Exit X (redundant-safe for small screens) */}
      <button
        type="button"
        onClick={onExit}
        aria-label="Exit voice mode"
        className="absolute bottom-6 right-6 z-20 flex h-9 w-9 items-center justify-center rounded-full border border-hairline bg-paper/70 text-ink-soft transition-all hover:border-ink/40 hover:text-ink md:hidden"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
