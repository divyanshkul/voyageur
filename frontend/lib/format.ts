export function inr(amount: number | null | undefined): string {
  if (amount == null) return "—"
  return `₹${amount.toLocaleString("en-IN")}`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—"
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, "0")}`
}

export function maskPhone(phone: string): string {
  if (!phone) return ""
  const digits = phone.replace(/\D/g, "")
  if (digits.length < 6) return phone
  return `${digits.slice(0, 3)} •• ${digits.slice(-3)}`
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("")
}

export function nightCount(checkIn: string, checkOut: string): number {
  const a = new Date(checkIn).getTime()
  const b = new Date(checkOut).getTime()
  if (Number.isNaN(a) || Number.isNaN(b)) return 0
  return Math.max(0, Math.round((b - a) / 86400000))
}

export function shortDate(value: string): string {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
  })
}

export function stageIndex(
  stage:
    | "collecting"
    | "researching"
    | "approving"
    | "calling"
    | "compiling"
    | "done"
): number {
  const map = {
    collecting: 0,
    researching: 1,
    approving: 1,
    calling: 2,
    compiling: 3,
    done: 3,
  } as const
  return map[stage]
}
