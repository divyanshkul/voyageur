"use client"

import ReactMarkdown from "react-markdown"
import type { ChatMessage as ChatMessageT } from "@/lib/types"
import { cn } from "@/lib/utils"

interface ChatMessageProps {
  message: ChatMessageT
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user"
  const time = message.timestamp.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  })

  if (isUser) {
    return (
      <div className="flex justify-end voy-rise">
        <div className="flex max-w-[78%] flex-col items-end gap-1">
          <div className="rounded-[14px] rounded-br-[4px] bg-ink px-4 py-2.5 text-[14.5px] leading-snug text-paper shadow-[0_8px_24px_-14px_oklch(0.2_0.02_60/0.4)]">
            {message.content}
          </div>
          <span suppressHydrationWarning className="num text-[10px] tracking-[0.1em] text-ink-soft/60 pr-1.5">
            {time}
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex voy-rise">
      <div className="flex max-w-[82%] flex-col gap-1.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-ink text-paper num text-[10px] tracking-wider">
            V
          </div>
          <span className="eyebrow">Concierge</span>
          <span suppressHydrationWarning className="num text-[10px] text-ink-soft/60">· {time}</span>
        </div>
        <div
          className={cn(
            "pl-8.5 text-[15px] leading-[1.55] text-ink",
            "[&_p]:mb-2 [&_p:last-child]:mb-0 [&_strong]:font-medium [&_strong]:text-ink",
            "[&_em]:font-display [&_em]:italic [&_em]:text-cognac",
            "[&_ul]:mt-2 [&_ul]:mb-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:text-ink-soft",
            "[&_ol]:mt-2 [&_ol]:mb-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:text-ink-soft",
            "[&_li]:my-0.5",
            "[&_code]:rounded [&_code]:bg-canvas [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[13px] [&_code]:font-mono [&_code]:text-cognac",
            "[&_a]:text-cognac [&_a]:underline [&_a]:underline-offset-2"
          )}
          style={{ paddingLeft: "34px" }}
        >
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}

export function TypingIndicator() {
  return (
    <div className="flex voy-rise">
      <div className="flex items-center gap-2.5">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-ink text-paper num text-[10px] tracking-wider">
          V
        </div>
        <div className="flex items-center gap-1.5 rounded-full border border-hairline bg-paper px-3 py-1.5">
          <span
            className="h-1.5 w-1.5 rounded-full bg-cognac voy-dot-pulse"
            style={{ animationDelay: "0ms" }}
          />
          <span
            className="h-1.5 w-1.5 rounded-full bg-cognac voy-dot-pulse"
            style={{ animationDelay: "180ms" }}
          />
          <span
            className="h-1.5 w-1.5 rounded-full bg-cognac voy-dot-pulse"
            style={{ animationDelay: "360ms" }}
          />
        </div>
      </div>
    </div>
  )
}
