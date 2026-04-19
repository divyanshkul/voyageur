"use client"

import { MapPin, Phone, Sparkles, Star } from "lucide-react"
import type { Report } from "@/lib/types"
import { inr, nightCount, shortDate } from "@/lib/format"
import { SavingsBadge } from "./SavingsBadge"
import { ComparisonTable } from "./ComparisonTable"

interface ReportViewProps {
  report: Report
}

export function ReportView({ report }: ReportViewProps) {
  const { top_pick, comparisons, preferences, average_savings_percent, summary } =
    report

  const nights = preferences
    ? nightCount(preferences.check_in, preferences.check_out)
    : 0

  const topSavings = top_pick?.savings_amount ?? null
  const topPrice = top_pick?.direct_price ?? top_pick?.ota_price ?? null

  return (
    <div className="flex flex-col gap-6">
      {/* Top pick — the hero moment */}
      {top_pick && (
        <div className="relative overflow-hidden rounded-[20px] border border-hairline bg-paper paper">
          {/* Decorative band */}
          <div className="absolute inset-x-0 top-0 h-[4px] bg-gradient-to-r from-cognac via-saffron to-sage" />

          <div className="grid grid-cols-1 gap-6 p-8 md:grid-cols-[1.4fr_1fr]">
            {/* Left: hotel + price */}
            <div>
              <div className="eyebrow flex items-center gap-2">
                <Sparkles className="h-3 w-3 text-cognac" strokeWidth={2} />
                Top Pick
              </div>
              <h2 className="mt-3 font-display text-[40px] leading-[1] tracking-tight text-ink">
                {top_pick.hotel.name}
              </h2>
              <div className="mt-2 flex items-center gap-3 text-[13px] text-ink-soft">
                <span className="flex items-center gap-1">
                  <Star
                    className="h-3.5 w-3.5 fill-saffron text-saffron"
                    strokeWidth={1}
                  />
                  <span className="num text-ink">
                    {top_pick.hotel.rating.toFixed(1)}
                  </span>
                </span>
                <span className="h-3 w-px bg-hairline" />
                <span className="flex items-center gap-1">
                  <MapPin className="h-3 w-3" strokeWidth={1.5} />
                  <span className="truncate max-w-[260px]">
                    {top_pick.hotel.address}
                  </span>
                </span>
              </div>

              {summary && (
                <p className="mt-5 max-w-md font-display italic text-[17px] leading-snug text-ink-soft">
                  &ldquo;{summary}&rdquo;
                </p>
              )}

              <div className="mt-6 flex items-center gap-3">
                <a
                  href={`tel:${top_pick.hotel.phone}`}
                  className="group inline-flex items-center gap-2 rounded-full bg-ink px-5 py-2.5 text-[13.5px] font-medium text-paper transition-all hover:bg-cognac"
                >
                  <Phone className="h-3.5 w-3.5" strokeWidth={2} />
                  Call to book
                  <span className="num text-[12px] text-paper/70 group-hover:text-paper">
                    {top_pick.hotel.phone}
                  </span>
                </a>
                <button
                  type="button"
                  className="rounded-full border border-hairline px-4 py-2 text-[13px] text-ink-soft hover:text-ink hover:border-ink/40"
                >
                  Share report
                </button>
              </div>
            </div>

            {/* Right: price block */}
            <div className="flex flex-col justify-center gap-4 rounded-2xl bg-canvas/60 p-6">
              <div className="flex items-center justify-between gap-4">
                <span className="eyebrow">Direct rate</span>
                <SavingsBadge percent={top_pick.savings_percent} size="md" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="num text-[48px] leading-none text-ink">
                  {inr(topPrice)}
                </span>
                <span className="text-[13px] text-ink-soft">
                  per night
                </span>
              </div>
              <div className="flex items-center justify-between border-t border-hairline pt-3 text-[12px]">
                <div>
                  <div className="eyebrow text-[9.5px]">OTA</div>
                  <div className="num mt-1 text-ink-soft line-through">
                    {inr(top_pick.ota_price)}
                  </div>
                </div>
                <div className="text-right">
                  <div className="eyebrow text-[9.5px]">You save</div>
                  <div className="num mt-1 text-sage font-medium">
                    {inr(topSavings)}
                    {nights > 0 && topSavings ? (
                      <span className="text-ink-soft text-[11px]">
                        {" "}
                        · {inr(topSavings * nights)} over {nights}n
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-0 overflow-hidden rounded-2xl border border-hairline bg-paper divide-x divide-hairline">
        <StatCell
          label="Hotels called"
          value={comparisons.length.toString()}
          sub="direct line"
        />
        <StatCell
          label="Average savings"
          value={
            average_savings_percent != null
              ? `${average_savings_percent.toFixed(0)}%`
              : "—"
          }
          sub="vs. OTA"
          highlight
        />
        <StatCell
          label="Trip dates"
          value={
            preferences
              ? `${shortDate(preferences.check_in)} – ${shortDate(preferences.check_out)}`
              : "—"
          }
          sub={`${nights} night${nights === 1 ? "" : "s"}`}
        />
      </div>

      {/* Comparison table */}
      <div>
        <div className="mb-3 flex items-end justify-between">
          <div>
            <div className="eyebrow">The ledger</div>
            <h3 className="mt-1 font-display text-[22px] leading-none tracking-tight text-ink">
              Every call, <em className="display-italic text-cognac">side by side</em>
            </h3>
          </div>
          <span className="num text-[11px] tracking-[0.14em] uppercase text-ink-soft">
            sorted by savings
          </span>
        </div>
        <ComparisonTable
          comparisons={comparisons}
          topPickId={top_pick?.hotel.place_id}
        />
      </div>
    </div>
  )
}

function StatCell({
  label,
  value,
  sub,
  highlight,
}: {
  label: string
  value: string
  sub: string
  highlight?: boolean
}) {
  return (
    <div className="flex flex-col gap-1 px-6 py-5">
      <span className="eyebrow text-[10px]">{label}</span>
      <span
        className={`font-display text-[30px] leading-none tracking-tight ${
          highlight ? "text-cognac" : "text-ink"
        }`}
      >
        {value}
      </span>
      <span className="text-[11px] text-ink-soft">{sub}</span>
    </div>
  )
}
