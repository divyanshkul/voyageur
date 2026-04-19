"use client"

import Link from "next/link"
import { ArrowUpRight, Phone, Search, MessageSquare, FileText } from "lucide-react"

export default function LandingPage() {
  return (
    <div className="relative isolate min-h-screen w-full overflow-x-hidden">
      <Masthead />

      {/* ———— HERO ———— */}
      <section className="relative px-6 pt-16 md:px-14 md:pt-20 lg:px-20">
        <div className="mx-auto grid max-w-[1280px] grid-cols-12 gap-8">
          {/* Headline */}
          <div className="col-span-12 relative">
            <div className="voy-rise" style={{ animationDelay: "120ms" }}>
              <h1 className="display text-[clamp(54px,9vw,128px)] leading-[0.96] tracking-[-0.02em] text-ink">
                Your travel concierge
                <br />
                <span className="display-italic text-cognac">that picks up</span>
                <br />
                <span className="display-italic text-ink">the phone.</span>
              </h1>
            </div>

            {/* Decorative compass, offset */}
            <Compass className="pointer-events-none absolute -right-6 top-2 hidden h-40 w-40 text-cognac/40 lg:block" />

            <div className="mt-10 grid grid-cols-12 gap-8">
              <p className="col-span-12 md:col-span-7 voy-rise text-[17px] leading-[1.55] text-ink" style={{ animationDelay: "220ms" }}>
                <span className="float-left mr-2 mt-1 font-display text-[64px] leading-[0.8] text-cognac">
                  T
                </span>
                ell it where you're going. It reads your plans, scouts the
                stays, the tables, the drivers, the quiet corners worth the
                detour. Then it picks up the phone, in your language, and
                brings back confirmations and prices nobody posts online. No
                tabs. No chasing. Just your trip, laid out.
              </p>

              <div className="col-span-12 md:col-span-5 flex flex-col items-start justify-end gap-5 voy-rise" style={{ animationDelay: "320ms" }}>
                <div className="flex items-center gap-3">
                  <StartPlanningButton />
                  <Link
                    href="/landing#method"
                    className="group inline-flex items-center gap-1.5 text-[13px] text-ink-soft transition-colors hover:text-ink"
                  >
                    <span className="font-display italic">read the method</span>
                    <span className="transition-transform group-hover:translate-x-0.5">→</span>
                  </Link>
                </div>
                <div className="flex items-center gap-3 text-[10.5px] tracking-[0.22em] uppercase text-ink-soft/80">
                  <span className="flex h-1.5 w-1.5 rounded-full bg-sage voy-dot-pulse" />
                  <span>Live in Bengaluru · free beta</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ———— BY THE NUMBERS ———— */}
      <section className="relative mt-28 px-6 md:px-14 lg:px-20">
        <div className="mx-auto max-w-[1280px]">
          <div className="hairline-divider" />
          <div className="grid grid-cols-2 gap-y-10 py-10 md:grid-cols-4">
            <Stat kpi="18%" label="Average saved vs. listed rates" />
            <Stat kpi="2,431" label="Calls placed by the concierge" />
            <Stat kpi="47s" label="Median ring-to-answer time" />
            <Stat kpi="24" label="Destinations, and counting" />
          </div>
          <div className="hairline-divider" />
        </div>
      </section>

      {/* ———— THE METHOD ———— */}
      <section id="method" className="relative mt-24 px-6 md:px-14 lg:px-20">
        <div className="mx-auto max-w-[1280px]">
          <div className="grid grid-cols-12 gap-8">
            <div className="col-span-12 md:col-span-4">
              <div className="eyebrow">Feature · II</div>
              <h2 className="mt-4 display text-[clamp(36px,5vw,64px)] leading-[1.02] text-ink">
                The method,
                <br />
                <span className="display-italic text-cognac">in four moves.</span>
              </h2>
              <p className="mt-5 max-w-[36ch] text-[14.5px] leading-relaxed text-ink-soft">
                What happens between your first sentence and the finished
                itinerary, narrated, for the first time, by the concierge
                itself.
              </p>
            </div>

            <div className="col-span-12 md:col-span-8">
              <ol className="flex flex-col">
                <Method
                  roman="I"
                  title="The Briefing"
                  body="Tell us in plain language. A destination, a mood, the dates that matter, a budget that quietly matters more. A lake view, a late dinner, a driver you can trust. We read between the lines."
                  icon={MessageSquare}
                />
                <Method
                  roman="II"
                  title="The Scouting"
                  body="We shortlist the stays, the tables, the routes that actually fit, not the ones paying for placement. You glance over, approve what's worth a call."
                  icon={Search}
                />
                <Method
                  roman="III"
                  title="The Calls"
                  body="Our AI dials the front desks, the restaurants, the operators, whoever holds the real answer. In the local language, asking the awkward questions, negotiating on your behalf."
                  icon={Phone}
                  accent
                />
                <Method
                  roman="IV"
                  title="The Itinerary"
                  body="A clean, single-page brief. Real rates, confirmations, what we heard, what we'd quietly recommend. Yours to act on, or to send to the group."
                  icon={FileText}
                  last
                />
              </ol>
            </div>
          </div>
        </div>
      </section>

      {/* ———— PULL QUOTE ———— */}
      <section className="relative mt-28 px-6 md:px-14 lg:px-20">
        <div className="mx-auto max-w-[1120px]">
          <div className="paper relative rounded-2xl px-10 py-14 md:px-20 md:py-20">
            <div className="absolute left-6 top-6 eyebrow">Marginalia</div>
            <div className="absolute right-6 top-6 eyebrow num">₂₀₂₆</div>

            <blockquote className="relative">
              <span className="absolute -left-3 -top-8 font-display text-[96px] leading-none text-cognac/50 md:-left-6 md:text-[140px]">
                &ldquo;
              </span>
              <p className="display-italic text-[clamp(28px,4.2vw,52px)] leading-[1.15] text-ink">
                I sent Voyageur off at breakfast, forgot about it, and by lunch
                I had the whole trip laid out. The stay, a dinner reservation,
                a driver for the weekend. It's the{" "}
                <span className="text-cognac">first travel tool</span> that
                felt like it was working <em>for</em> me.
              </p>
            </blockquote>

            <div className="mt-10 flex items-center gap-4">
              <span className="h-px w-10 bg-ink-soft/40" />
              <div className="flex flex-col">
                <span className="num text-[11px] tracking-[0.22em] uppercase text-ink">
                  A. Menon
                </span>
                <span className="font-display italic text-[13px] text-ink-soft">
                  anniversary, Udaipur, five nights
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ———— DESTINATIONS / STARTERS ———— */}
      <section className="relative mt-28 px-6 md:px-14 lg:px-20">
        <div className="mx-auto max-w-[1280px]">
          <div className="flex items-end justify-between gap-6">
            <div>
              <div className="eyebrow">Dispatches · III</div>
              <h2 className="mt-3 display text-[clamp(30px,4vw,52px)] leading-[1.02] text-ink">
                A few briefs <span className="display-italic text-cognac">to begin with.</span>
              </h2>
            </div>
            <p className="hidden max-w-[28ch] text-[13px] leading-snug text-ink-soft md:block">
              Lift a line. Edit it. Send it. The concierge will take it
              from there.
            </p>
          </div>

          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-3">
            <BriefCard
              eyebrow="Monsoon · Coorg"
              line="Coorg, 4–6 Nov, two of us. A quiet stay under the rain, a coffee-estate breakfast, and someone who knows the drive in."
              note="weekend · stay + tours"
            />
            <BriefCard
              eyebrow="Anniversary · Udaipur"
              line="Udaipur, mid-Dec, ten years in. A lake-view room, a sunset boat, and a dinner table worth the flight."
              note="anniversary · stay + table"
              accent
            />
            <BriefCard
              eyebrow="Long weekend · Goa"
              line="Goa, Dec 14–16. Quiet beachfront, a scooter sorted for the morning, and a shack that closes its gate at ten."
              note="long weekend · stay + rides"
            />
          </div>
        </div>
      </section>

      {/* ———— CLOSING CTA ———— */}
      <section className="relative mt-32 px-6 pb-24 md:px-14 lg:px-20">
        <div className="mx-auto max-w-[1280px]">
          <div className="relative overflow-hidden rounded-[28px] border border-hairline bg-ink px-10 py-16 text-paper md:px-20 md:py-24">
            {/* Background flourish */}
            <Compass className="pointer-events-none absolute -right-12 -top-12 h-72 w-72 text-cognac/20" />
            <Compass className="pointer-events-none absolute -bottom-20 -left-20 h-96 w-96 text-paper/5" />

            <div className="relative grid grid-cols-12 gap-8">
              <div className="col-span-12 md:col-span-8">
                <div className="flex items-center gap-3">
                  <span className="h-1.5 w-1.5 rounded-full bg-cognac voy-dot-pulse" />
                  <span className="num text-[10.5px] tracking-[0.3em] uppercase text-paper/70">
                    The Concierge Desk · Open
                  </span>
                </div>
                <h2 className="mt-6 display text-[clamp(40px,6vw,88px)] leading-[0.98] text-paper">
                  A travel concierge
                  <br />
                  <span className="display-italic text-cognac">that dials in.</span>
                </h2>
                <p className="mt-6 max-w-[46ch] text-[15px] leading-relaxed text-paper/70">
                  One sentence is enough. We'll scout the stays, book the
                  tables, make the calls, and send back a single page with your
                  trip laid out.
                </p>
              </div>

              <div className="col-span-12 flex flex-col items-start justify-end gap-4 md:col-span-4 md:items-end">
                <StartPlanningButton variant="light" />
                <div className="flex items-center gap-3 text-[10.5px] tracking-[0.22em] uppercase text-paper/50">
                  <span>No card, no wait</span>
                  <span className="h-3 w-px bg-paper/20" />
                  <span className="num">≈ 3 min</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <Colophon />
    </div>
  )
}

/* ————————————————————————————————————————————————————————————————
   Masthead — newspaper-style header
   ———————————————————————————————————————————————————————————————— */
function Masthead() {
  return (
    <header className="relative z-20 border-b border-hairline bg-canvas/70 backdrop-blur">
      <div className="mx-auto flex max-w-[1280px] items-center justify-between px-6 py-5 md:px-14 lg:px-20">
        <div className="flex items-center gap-3">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            className="text-cognac"
            aria-hidden
          >
            <path
              d="M12 2.5 L20 20 L12 15.5 L4 20 Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
          <span className="num text-[11px] tracking-[0.3em] text-ink">
            VOYAGEUR
          </span>
          <span className="h-3 w-px bg-hairline" />
          <span className="font-display italic text-[13px] text-ink-soft">
            an AI travel concierge
          </span>
        </div>

        <nav className="hidden items-center gap-7 md:flex">
          <a
            href="#method"
            className="eyebrow hover:text-ink transition-colors"
          >
            Method
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <span className="hidden num text-[10.5px] tracking-[0.22em] uppercase text-ink-soft md:inline">
            19 · IV · MMXXVI
          </span>
          <Link
            href="/"
            className="group inline-flex items-center gap-1.5 rounded-full border border-hairline bg-paper px-3.5 py-1.5 text-[11.5px] text-ink transition-all hover:border-ink/40"
          >
            <span className="font-display italic">open</span>
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" strokeWidth={1.8} />
          </Link>
        </div>
      </div>
    </header>
  )
}

/* ————————————————————————————————————————————————————————————————
   Start Planning button — the marquee CTA
   ———————————————————————————————————————————————————————————————— */
function StartPlanningButton({ variant = "dark" }: { variant?: "dark" | "light" }) {
  const isDark = variant === "dark"
  return (
    <Link
      href="/"
      className={[
        "group relative inline-flex items-center gap-3 overflow-hidden rounded-full px-6 py-3.5 transition-all",
        isDark
          ? "bg-ink text-paper hover:bg-cognac hover:shadow-[0_20px_50px_-20px_oklch(0.52_0.14_45/0.55)]"
          : "bg-paper text-ink hover:bg-cognac hover:text-paper hover:shadow-[0_20px_50px_-20px_oklch(0.52_0.14_45/0.55)]",
      ].join(" ")}
    >
      {/* Shimmer sweep on hover */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full"
      />
      <span className="relative font-display italic text-[17px] leading-none">
        Start planning
      </span>
      <span className="relative flex h-7 w-7 items-center justify-center rounded-full bg-paper/10 transition-transform group-hover:translate-x-0.5">
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          className={isDark ? "text-paper" : "text-ink group-hover:text-paper"}
          aria-hidden
        >
          <path
            d="M2 7h10m0 0L8 3m4 4-4 4"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    </Link>
  )
}

/* ————————————————————————————————————————————————————————————————
   Stat
   ———————————————————————————————————————————————————————————————— */
function Stat({ kpi, label }: { kpi: string; label: string }) {
  return (
    <div className="flex flex-col border-l border-hairline pl-6 first:border-l-0 first:pl-0 md:first:border-l md:first:pl-6">
      <span className="display num text-[42px] leading-none text-ink md:text-[56px]">
        {kpi}
      </span>
      <span className="mt-3 max-w-[22ch] text-[11.5px] tracking-[0.14em] uppercase text-ink-soft">
        {label}
      </span>
    </div>
  )
}

/* ————————————————————————————————————————————————————————————————
   Method row
   ———————————————————————————————————————————————————————————————— */
function Method({
  roman,
  title,
  body,
  icon: Icon,
  accent = false,
  last = false,
}: {
  roman: string
  title: string
  body: string
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>
  accent?: boolean
  last?: boolean
}) {
  return (
    <li
      className={[
        "group relative grid grid-cols-12 items-start gap-6 py-7",
        last ? "" : "border-b border-hairline",
      ].join(" ")}
    >
      <div className="col-span-2 flex items-center gap-3">
        <span className="num text-[11px] tracking-[0.22em] text-ink-soft">
          {roman}
        </span>
      </div>
      <div className="col-span-8 flex items-start gap-4">
        <span
          className={[
            "mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border",
            accent
              ? "border-cognac bg-cognac-soft text-cognac"
              : "border-hairline bg-paper text-ink",
          ].join(" ")}
        >
          <Icon className="h-4 w-4" strokeWidth={1.5} />
        </span>
        <div>
          <h3 className="display text-[26px] leading-[1.1] text-ink">
            {title}
          </h3>
          <p className="mt-2 max-w-[52ch] text-[14.5px] leading-relaxed text-ink-soft">
            {body}
          </p>
        </div>
      </div>
      <div className="col-span-2 hidden justify-end md:flex">
        <span
          className={[
            "h-px w-16 self-center transition-all",
            accent ? "bg-cognac" : "bg-hairline group-hover:bg-ink-soft/50",
          ].join(" ")}
        />
      </div>
    </li>
  )
}

/* ————————————————————————————————————————————————————————————————
   Brief card — sample prompts presented as magazine dispatches
   ———————————————————————————————————————————————————————————————— */
function BriefCard({
  eyebrow,
  line,
  note,
  accent = false,
}: {
  eyebrow: string
  line: string
  note: string
  accent?: boolean
}) {
  return (
    <Link
      href="/"
      className={[
        "group relative flex h-full flex-col justify-between rounded-2xl border px-6 py-7 transition-all",
        accent
          ? "border-cognac/40 bg-cognac-soft/40 hover:border-cognac"
          : "border-hairline bg-paper hover:border-ink/30",
        "hover:shadow-[0_30px_60px_-40px_oklch(0.2_0.02_60/0.3)] hover:-translate-y-0.5",
      ].join(" ")}
    >
      <div>
        <div className="flex items-center justify-between">
          <span className="eyebrow">{eyebrow}</span>
          <ArrowUpRight
            className="h-4 w-4 text-ink-soft transition-all group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-cognac"
            strokeWidth={1.5}
          />
        </div>
        <p className="mt-5 font-display italic text-[22px] leading-[1.25] text-ink">
          &ldquo;{line}&rdquo;
        </p>
      </div>
      <div className="mt-8 flex items-center gap-3 text-[10.5px] tracking-[0.22em] uppercase text-ink-soft/80">
        <span className="h-px w-6 bg-ink-soft/40" />
        <span>{note}</span>
      </div>
    </Link>
  )
}

/* ————————————————————————————————————————————————————————————————
   Colophon / Footer
   ———————————————————————————————————————————————————————————————— */
function Colophon() {
  return (
    <footer className="relative border-t border-hairline bg-paper/40">
      <div className="mx-auto grid max-w-[1280px] grid-cols-12 gap-8 px-6 py-10 md:px-14 lg:px-20">
        <div className="col-span-12 md:col-span-6">
          <div className="flex items-center gap-3">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              className="text-cognac"
              aria-hidden
            >
              <path
                d="M12 2.5 L20 20 L12 15.5 L4 20 Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </svg>
            <span className="num text-[11px] tracking-[0.3em] text-ink">
              VOYAGEUR
            </span>
          </div>
          <p className="mt-4 max-w-[44ch] font-display italic text-[15px] leading-snug text-ink-soft">
            Set in Instrument Serif & Geist. Printed on a warm canvas.
            Composed and dispatched from Bengaluru, with a working phone line.
          </p>
        </div>

        <div className="col-span-6 md:col-span-3">
          <div className="eyebrow">Editorial</div>
          <ul className="mt-4 flex flex-col gap-2 text-[13px] text-ink-soft">
            <li><a href="#method" className="hover:text-ink transition-colors">The Method</a></li>
            <li><a href="#" className="hover:text-ink transition-colors">Dispatches</a></li>
            <li><a href="#" className="hover:text-ink transition-colors">Archive</a></li>
          </ul>
        </div>

        <div className="col-span-6 md:col-span-3">
          <div className="eyebrow">The Desk</div>
          <ul className="mt-4 flex flex-col gap-2 text-[13px] text-ink-soft">
            <li><Link href="/" className="hover:text-ink transition-colors">Start planning →</Link></li>
            <li><a href="#" className="hover:text-ink transition-colors">Press</a></li>
            <li><a href="#" className="hover:text-ink transition-colors">Say hello</a></li>
          </ul>
        </div>
      </div>

      <div className="border-t border-hairline">
        <div className="mx-auto flex max-w-[1280px] items-center justify-between px-6 py-5 md:px-14 lg:px-20">
          <span className="num text-[10.5px] tracking-[0.22em] uppercase text-ink-soft/70">
            © MMXXVI · Voyageur Press
          </span>
          <span className="font-display italic text-[13px] text-ink-soft">
            bon voyage,
          </span>
        </div>
      </div>
    </footer>
  )
}

/* ————————————————————————————————————————————————————————————————
   Compass — decorative SVG, rotates slowly
   ———————————————————————————————————————————————————————————————— */
function Compass({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 200 200"
      fill="none"
      className={`${className} animate-[spin_80s_linear_infinite] [transform-origin:50%_50%]`}
      aria-hidden
    >
      <circle cx="100" cy="100" r="78" stroke="currentColor" strokeWidth="0.8" />
      <circle cx="100" cy="100" r="60" stroke="currentColor" strokeWidth="0.6" />
      <circle cx="100" cy="100" r="40" stroke="currentColor" strokeWidth="0.5" />
      {Array.from({ length: 32 }).map((_, i) => {
        const angle = (i * Math.PI * 2) / 32
        const x1 = 100 + Math.cos(angle) * 78
        const y1 = 100 + Math.sin(angle) * 78
        const x2 = 100 + Math.cos(angle) * (i % 4 === 0 ? 68 : 74)
        const y2 = 100 + Math.sin(angle) * (i % 4 === 0 ? 68 : 74)
        return (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="currentColor"
            strokeWidth={i % 8 === 0 ? 1.2 : 0.6}
          />
        )
      })}
      <path
        d="M100 30 L108 100 L100 170 L92 100 Z"
        fill="currentColor"
        opacity="0.55"
      />
      <path
        d="M30 100 L100 108 L170 100 L100 92 Z"
        fill="currentColor"
        opacity="0.25"
      />
      <circle cx="100" cy="100" r="3" fill="currentColor" />
    </svg>
  )
}
