"use client"

import type { VoiceState } from "@/hooks/useVoiceTurn"
import { cn } from "@/lib/utils"

interface VoiceOrbProps {
  state: VoiceState
  level?: number // 0..1 mic RMS
  size?: number // px
}

/**
 * Large animated orb — the centerpiece of the voice onboarding.
 * Reacts distinctly to each state for immediate visual feedback.
 */
export function VoiceOrb({ state, level = 0, size = 260 }: VoiceOrbProps) {
  const scale = state === "listening" ? 1 + level * 0.22 : 1

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      {/* Outer soft halo — always breathing */}
      <div
        className="absolute inset-0 rounded-full"
        style={{
          background:
            "radial-gradient(closest-side, oklch(0.52 0.14 45 / 0.22), transparent 70%)",
          filter: "blur(22px)",
          animation: "voy-orb-breathe 4.5s ease-in-out infinite",
        }}
      />

      {/* Speaking: expanding cognac rings */}
      {state === "speaking" && (
        <>
          <span
            className="absolute rounded-full border border-cognac/60"
            style={{
              width: size * 0.82,
              height: size * 0.82,
              animation: "voy-ring-soft 1.9s ease-out infinite",
            }}
          />
          <span
            className="absolute rounded-full border border-cognac/40"
            style={{
              width: size * 0.82,
              height: size * 0.82,
              animation: "voy-ring-soft 1.9s ease-out 0.65s infinite",
            }}
          />
        </>
      )}

      {/* Listening: ink ring + reactive core */}
      {state === "listening" && (
        <span
          className="absolute rounded-full border border-ink/30"
          style={{
            width: size * 0.9,
            height: size * 0.9,
            animation: "voy-ring-soft 2.2s ease-out infinite",
          }}
        />
      )}

      {/* Thinking: slow-rotating dashed ring */}
      {state === "thinking" && (
        <span
          className="absolute rounded-full"
          style={{
            width: size * 0.92,
            height: size * 0.92,
            border: "1.5px dashed oklch(0.52 0.14 45 / 0.5)",
            animation: "voy-spin 3.2s linear infinite",
          }}
        />
      )}

      {/* Core orb */}
      <div
        className={cn(
          "relative rounded-full transition-transform duration-150 ease-out",
          state === "idle" && "scale-100",
        )}
        style={{
          width: size * 0.68,
          height: size * 0.68,
          transform: `scale(${scale})`,
          background:
            state === "listening"
              ? "radial-gradient(circle at 30% 25%, oklch(0.94 0.04 58) 0%, oklch(0.52 0.14 45) 62%, oklch(0.35 0.12 40) 100%)"
              : state === "speaking"
                ? "radial-gradient(circle at 30% 25%, oklch(0.96 0.03 80) 0%, oklch(0.78 0.14 75) 55%, oklch(0.52 0.14 45) 100%)"
                : state === "thinking"
                  ? "radial-gradient(circle at 30% 25%, oklch(0.95 0.02 80) 0%, oklch(0.82 0.06 75) 55%, oklch(0.55 0.08 50) 100%)"
                  : "radial-gradient(circle at 30% 25%, oklch(0.97 0.015 80) 0%, oklch(0.88 0.04 58) 55%, oklch(0.62 0.12 45) 100%)",
          boxShadow:
            "0 20px 60px -20px oklch(0.52 0.14 45 / 0.5), inset 0 3px 12px oklch(1 0 0 / 0.45), inset 0 -20px 40px oklch(0.2 0.02 60 / 0.25)",
        }}
      >
        {/* Specular highlight */}
        <div
          className="absolute rounded-full"
          style={{
            top: "10%",
            left: "18%",
            width: "38%",
            height: "28%",
            background:
              "radial-gradient(closest-side, oklch(1 0 0 / 0.7), transparent 70%)",
            filter: "blur(4px)",
          }}
        />

        {/* Thinking shimmer overlay */}
        {state === "thinking" && (
          <div
            className="absolute inset-0 rounded-full overflow-hidden"
            style={{
              mask: "radial-gradient(circle, black 0%, black 70%, transparent 90%)",
              WebkitMask:
                "radial-gradient(circle, black 0%, black 70%, transparent 90%)",
            }}
          >
            <div className="absolute inset-0 voy-shimmer" />
          </div>
        )}
      </div>

      {/* Inline keyframes — co-located so this component is drop-in */}
      <style jsx>{`
        @keyframes voy-orb-breathe {
          0%,
          100% {
            transform: scale(1);
            opacity: 0.85;
          }
          50% {
            transform: scale(1.06);
            opacity: 1;
          }
        }
        @keyframes voy-spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  )
}
