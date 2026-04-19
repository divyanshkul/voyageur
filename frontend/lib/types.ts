export interface TravelPreferences {
  destination: string
  check_in: string
  check_out: string
  budget_min: number | null
  budget_max: number
  guests: number
  star_rating: number | null
  food_pref: "veg" | "non-veg" | "both"
  smoking: boolean
  alcohol: boolean
  amenities: string[]
  language_pref: "kannada" | "hindi" | "english"
  special_requests: string | null
}

export interface Hotel {
  place_id: string
  name: string
  phone: string
  address: string
  rating: number
  ota_price: number | null
  photo_url: string | null
  amenities: string[]
  match_score: number | null
}

export interface CallResult {
  hotel: Hotel
  status: "completed" | "no_answer" | "voicemail" | "failed"
  direct_price: number | null
  availability: boolean | null
  promotions: string | null
  cancellation_policy: string | null
  transcript: string | null
  call_duration: number | null
}

export interface HotelComparison {
  hotel: Hotel
  call_result: CallResult
  ota_price: number | null
  direct_price: number | null
  savings_amount: number | null
  savings_percent: number | null
  verdict: "cheaper" | "same" | "more_expensive" | "unknown"
}

export interface Report {
  preferences: TravelPreferences
  comparisons: HotelComparison[]
  top_pick: HotelComparison | null
  average_savings_percent: number | null
  summary: string
  markdown: string
}

export type Stage =
  | "collecting"
  | "researching"
  | "approving"
  | "calling"
  | "compiling"
  | "done"

export type WSEvent =
  | { event: "stage_change"; stage: Stage }
  | { event: "hotels_found"; count: number; hotels: Hotel[] }
  | { event: "call_started"; hotel: string }
  | { event: "call_update"; hotel: string; status: string; duration: number }
  | {
      event: "call_completed"
      hotel: string
      price: number | null
      available: boolean
    }
  | { event: "report_ready"; report: Report }

export interface ChatMessage {
  id: string
  role: "user" | "agent"
  content: string
  timestamp: Date
  hotels?: Hotel[]
  report?: Report
}

export interface SessionState {
  session_id: string
  stage: Stage
  preferences: TravelPreferences | null
  hotels: Hotel[]
  approved_hotels: Hotel[]
  call_results: CallResult[]
  report: Report | null
}

export type CallStatus =
  | "queued"
  | "ringing"
  | "connected"
  | "completed"
  | "no_answer"
  | "failed"
  | "retrying"

export interface LiveCall {
  hotel_name: string
  phone?: string
  status: CallStatus
  duration: number
  price: number | null
  available: boolean | null
}
