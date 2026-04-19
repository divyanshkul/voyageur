"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { sttTranscribe, ttsSpeak } from "@/lib/api"

export type VoiceState = "idle" | "speaking" | "listening" | "thinking"

interface UseVoiceTurnArgs {
  language?: string
  onTranscript?: (text: string) => void
  onError?: (err: Error) => void
}

function base64ToBlob(base64: string, mime = "audio/wav"): Blob {
  const bin = atob(base64)
  const arr = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i)
  return new Blob([arr], { type: mime })
}

export function useVoiceTurn({
  language = "en-IN",
  onTranscript,
  onError,
}: UseVoiceTurnArgs = {}) {
  const [state, setState] = useState<VoiceState>("idle")
  const [level, setLevel] = useState(0) // 0..1 smoothed mic RMS
  const [liveTranscript, setLiveTranscript] = useState<string>("")

  const audioElRef = useRef<HTMLAudioElement | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const rafRef = useRef<number | null>(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
      if (audioElRef.current) {
        audioElRef.current.pause()
        audioElRef.current.src = ""
      }
      streamRef.current?.getTracks().forEach((t) => t.stop())
      audioCtxRef.current?.close().catch(() => {})
      mediaRecorderRef.current = null
    }
  }, [])

  // --- TTS playback ---
  const speak = useCallback(
    async (text: string) => {
      if (!text.trim()) return
      setState("speaking")
      try {
        const b64 = await ttsSpeak(text, language)
        const blob = base64ToBlob(b64, "audio/wav")
        const url = URL.createObjectURL(blob)
        const el = audioElRef.current ?? new Audio()
        audioElRef.current = el
        el.src = url
        await new Promise<void>((resolve, reject) => {
          el.onended = () => resolve()
          el.onerror = () => reject(new Error("audio playback failed"))
          el.play().catch(reject)
        })
        URL.revokeObjectURL(url)
      } catch (e) {
        onError?.(e instanceof Error ? e : new Error(String(e)))
      } finally {
        setState("idle")
      }
    },
    [language, onError]
  )

  // --- mic level metering loop ---
  const startLevelLoop = useCallback(() => {
    const analyser = analyserRef.current
    if (!analyser) return
    const buf = new Uint8Array(analyser.fftSize)
    const tick = () => {
      analyser.getByteTimeDomainData(buf)
      let sumSq = 0
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128
        sumSq += v * v
      }
      const rms = Math.sqrt(sumSq / buf.length)
      setLevel((prev) => prev * 0.75 + rms * 0.25) // smooth
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
  }, [])

  // --- Start recording ---
  const startListening = useCallback(async () => {
    try {
      setLiveTranscript("")
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const ctx = new (window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
      audioCtxRef.current = ctx
      const source = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      source.connect(analyser)
      analyserRef.current = analyser
      startLevelLoop()

      // Pick best-supported format; webm/opus is default in Chrome.
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : ""
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data)
      }
      mediaRecorderRef.current = recorder
      recorder.start(100)
      setState("listening")
    } catch (e) {
      onError?.(e instanceof Error ? e : new Error(String(e)))
      setState("idle")
    }
  }, [onError, startLevelLoop])

  // --- Stop recording + transcribe ---
  const stopListening = useCallback(async (): Promise<string> => {
    const recorder = mediaRecorderRef.current
    if (!recorder) return ""

    setState("thinking")
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    setLevel(0)

    const stopped = new Promise<void>((resolve) => {
      recorder.onstop = () => resolve()
    })
    if (recorder.state !== "inactive") recorder.stop()
    await stopped

    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    audioCtxRef.current?.close().catch(() => {})
    audioCtxRef.current = null
    analyserRef.current = null

    const blob = new Blob(chunksRef.current, {
      type: recorder.mimeType || "audio/webm",
    })
    chunksRef.current = []

    try {
      const transcript = await sttTranscribe(blob)
      setLiveTranscript(transcript)
      onTranscript?.(transcript)
      setState("idle")
      return transcript
    } catch (e) {
      onError?.(e instanceof Error ? e : new Error(String(e)))
      setState("idle")
      return ""
    }
  }, [onError, onTranscript])

  const cancel = useCallback(() => {
    if (audioElRef.current) {
      audioElRef.current.pause()
      audioElRef.current.src = ""
    }
    if (mediaRecorderRef.current?.state !== "inactive") {
      mediaRecorderRef.current?.stop()
    }
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    audioCtxRef.current?.close().catch(() => {})
    audioCtxRef.current = null
    analyserRef.current = null
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    setLevel(0)
    setState("idle")
  }, [])

  return {
    state,
    level,
    liveTranscript,
    speak,
    startListening,
    stopListening,
    cancel,
  }
}
