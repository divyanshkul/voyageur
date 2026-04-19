"use client"

import { ArrowDown, ArrowUp, Minus } from "lucide-react"
import { cn } from "@/lib/utils"

interface SavingsBadgeProps {
  percent: number | null | undefined
  size?: "sm" | "md" | "lg"
  variant?: "chip" | "stat"
}

export function SavingsBadge({
  percent,
  size = "md",
  variant = "chip",
}: SavingsBadgeProps) {
  const isUnknown = percent == null
  const isPositive = !isUnknown && percent > 0
  const isNegative = !isUnknown && percent < 0
  const abs = isUnknown ? 0 : Math.abs(percent)

  const tone = isPositive
    ? {
        bg: "bg-sage-soft",
        text: "text-sage",
        border: "border-sage/50",
        icon: ArrowDown,
      }
    : isNegative
      ? {
          bg: "bg-[oklch(0.95_0.05_30/0.45)]",
          text: "text-clay",
          border: "border-clay/40",
          icon: ArrowUp,
        }
      : {
          bg: "bg-canvas",
          text: "text-ink-soft",
          border: "border-hairline",
          icon: Minus,
        }

  const Icon = tone.icon

  if (variant === "stat") {
    return (
      <div className="flex items-baseline gap-2">
        <span
          className={cn(
            "num tabular-nums leading-none",
            size === "lg" && "text-[64px]",
            size === "md" && "text-[42px]",
            size === "sm" && "text-[24px]",
            tone.text
          )}
        >
          {isUnknown ? "—" : `${abs.toFixed(0)}%`}
        </span>
        <span className="eyebrow text-[10.5px]">
          {isPositive ? "saved" : isNegative ? "over" : "tbd"}
        </span>
      </div>
    )
  }

  const sizeClasses =
    size === "lg"
      ? "text-[14px] px-3 py-1.5"
      : size === "sm"
        ? "text-[10.5px] px-2 py-0.5"
        : "text-[12px] px-2.5 py-1"

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border font-medium",
        sizeClasses,
        tone.bg,
        tone.text,
        tone.border
      )}
    >
      <Icon
        className={cn(
          size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3",
          tone.text
        )}
        strokeWidth={2.2}
      />
      <span className="num">
        {isUnknown ? "—" : `${isPositive ? "Save " : isNegative ? "+" : ""}${abs.toFixed(0)}%`}
      </span>
    </span>
  )
}
