import { useRef, useState } from "react"
import { Copy, ThumbsDown, ThumbsUp } from "lucide-react"

import { CitationChip } from "@/components/patterns/citation-chip.tsx"
import { OutcomeBadge } from "@/components/patterns/outcome-badge.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { SourceList } from "@/components/patterns/source-list.tsx"
import { StreamingCaret } from "@/components/patterns/streaming-caret.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import type {
  AssistantPhase,
  CitationView,
  FeedbackState,
} from "@/features/ask/types.ts"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

export function AssistantMessage({
  phase,
  text,
  outgoing,
  citations,
  outcome,
  replaced,
  errorMessage,
  requestId,
  feedback,
  canAnswer,
  onFeedback,
  onRetry,
}: {
  phase: AssistantPhase
  text: string
  outgoing: string | null
  citations: CitationView[]
  outcome: string | null
  replaced: boolean
  errorMessage: string | null
  requestId: string | null
  feedback: FeedbackState
  canAnswer: boolean
  onFeedback: (rating: 1 | -1) => void
  onRetry: () => void
}) {
  const rootRef = useRef<HTMLElement>(null)
  const { reduced } = useMotion()
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const busy = phase === "waiting" || phase === "streaming"
  const citationKey = citations.map((citation) => citation.chunkId).join(",")

  useGSAP(
    () => {
      presets.enterAssistant(rootRef.current, reduced)
    },
    { scope: rootRef }
  )

  useGSAP(
    () => {
      if (!replaced) {
        return
      }
      presets.replaceAnswer(rootRef.current, reduced)
    },
    { scope: rootRef, dependencies: [replaced, reduced] }
  )

  useGSAP(
    () => {
      const chips = rootRef.current?.querySelectorAll("[data-citation]")
      if (!chips || chips.length === 0) {
        return
      }
      presets.enterCitations(chips, reduced)
    },
    { scope: rootRef, dependencies: [citationKey, reduced] }
  )

  function openSource(chunkId: string) {
    setSourcesOpen(true)
    window.requestAnimationFrame(() => {
      document.getElementById(`source-${chunkId}`)?.focus()
    })
  }

  return (
    <article
      ref={rootRef}
      aria-busy={busy}
      data-phase={phase}
      className="flex max-w-full flex-col gap-3"
    >
      {phase === "waiting" ? <WaitingLines /> : null}
      {phase === "streaming" || phase === "done" ? (
        <AnswerBody
          phase={phase}
          text={text}
          outgoing={outgoing}
          citations={citations}
          outcome={outcome}
          replaced={replaced}
          sourcesOpen={sourcesOpen}
          onOpenChange={setSourcesOpen}
          onSelect={openSource}
        />
      ) : null}
      {phase === "cancelled" ? <Interrupted onRetry={onRetry} /> : null}
      {phase === "error" ? (
        <StreamError
          message={errorMessage}
          requestId={requestId}
          onRetry={onRetry}
        />
      ) : null}
      {phase === "done" && canAnswer ? (
        <AnswerActions
          text={text}
          feedback={feedback}
          onFeedback={onFeedback}
        />
      ) : null}
    </article>
  )
}

function WaitingLines() {
  return (
    <div className="flex flex-col gap-2">
      <span className="sr-only">{pt.ask.waiting}</span>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-4/5" />
      <Skeleton className="h-4 w-2/3" />
      <StreamingCaret />
    </div>
  )
}

function AnswerBody({
  phase,
  text,
  outgoing,
  citations,
  outcome,
  replaced,
  sourcesOpen,
  onOpenChange,
  onSelect,
}: {
  phase: "streaming" | "done"
  text: string
  outgoing: string | null
  citations: CitationView[]
  outcome: string | null
  replaced: boolean
  sourcesOpen: boolean
  onOpenChange: (open: boolean) => void
  onSelect: (chunkId: string) => void
}) {
  if (phase === "done" && outcome === "refused") {
    return (
      <div
        role="alert"
        className="flex flex-col gap-3 rounded-2xl border border-danger bg-[color-mix(in_oklab,var(--danger)_15%,transparent)] p-4"
      >
        <OutcomeBadge kind="refused" />
        <p className="text-message whitespace-pre-wrap text-foreground">
          {text}
        </p>
      </div>
    )
  }

  return (
    <div className="relative flex flex-col gap-3">
      {replaced && outgoing ? (
        <p
          data-outgoing
          aria-hidden="true"
          className="absolute inset-x-0 top-0 text-message whitespace-pre-wrap text-foreground"
        >
          {outgoing}
        </p>
      ) : null}
      {phase === "done" && replaced ? (
        <>
          <p className="text-body text-foreground">{pt.ask.replacedNote}</p>
          <OutcomeBadge kind="replaced" />
        </>
      ) : null}
      {phase === "done" &&
      !replaced &&
      (outcome === "abstained" || outcome === "grounding_failed") ? (
        <OutcomeBadge kind="abstained" />
      ) : null}
      {phase === "done" && (outcome === "degraded" || outcome === "error") ? (
        <OutcomeBadge kind="unavailable" />
      ) : null}
      <p
        data-incoming
        className="text-message whitespace-pre-wrap text-foreground"
      >
        <AnswerPieces text={text} citations={citations} onSelect={onSelect} />
        {phase === "streaming" ? <StreamingCaret /> : null}
      </p>
      {phase === "done" ? (
        <SourceList
          citations={citations}
          open={sourcesOpen}
          onOpenChange={onOpenChange}
        />
      ) : null}
    </div>
  )
}

function AnswerPieces({
  text,
  citations,
  onSelect,
}: {
  text: string
  citations: CitationView[]
  onSelect: (chunkId: string) => void
}) {
  const pieces = text.split(/(\[\d+\])/g)
  return pieces.map((piece, index) => {
    const match = /^\[(\d+)\]$/.exec(piece)
    if (!match) {
      return <span key={`${index}-${piece}`}>{piece}</span>
    }
    const citationIndex = Number(match[1])
    const citation = citations.find((item) => item.index === citationIndex)
    if (!citation) {
      return <span key={`${index}-${piece}`}>{piece}</span>
    }
    return (
      <CitationChip
        key={`${citation.chunkId}-${index}`}
        index={citationIndex}
        onSelect={() => {
          onSelect(citation.chunkId)
        }}
      />
    )
  })
}

function Interrupted({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3">
      <p className="text-message text-foreground">{pt.ask.interrupted}</p>
      <Button type="button" className="min-h-11 md:min-h-8" onClick={onRetry}>
        {pt.ask.retry}
      </Button>
    </div>
  )
}

function StreamError({
  message,
  requestId,
  onRetry,
}: {
  message: string | null
  requestId: string | null
  onRetry: () => void
}) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3">
      <p className="text-message text-foreground">
        {message || pt.ask.couldNotFinish}
      </p>
      {requestId ? <RequestIdCopy requestId={requestId} /> : null}
      <Button type="button" className="min-h-11 md:min-h-8" onClick={onRetry}>
        {pt.ask.retry}
      </Button>
    </div>
  )
}

function AnswerActions({
  text,
  feedback,
  onFeedback,
}: {
  text: string
  feedback: FeedbackState
  onFeedback: (rating: 1 | -1) => void
}) {
  const [copied, setCopied] = useState(false)
  const rated = feedback !== null

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant={feedback === 1 ? "default" : "outline"}
          className="min-h-11 md:min-h-8"
          aria-pressed={feedback === 1}
          disabled={rated}
          onClick={() => {
            onFeedback(1)
          }}
        >
          <ThumbsUp />
          {pt.ask.useful}
        </Button>
        <Button
          type="button"
          variant={feedback === -1 ? "default" : "outline"}
          className="min-h-11 md:min-h-8"
          aria-pressed={feedback === -1}
          disabled={rated}
          onClick={() => {
            onFeedback(-1)
          }}
        >
          <ThumbsDown />
          {pt.ask.notUseful}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-11 md:min-h-8"
          onClick={() => {
            void copy()
          }}
        >
          <Copy />
          {copied ? pt.ask.copied : pt.ask.copy}
        </Button>
      </div>
      {feedback === "locked" ? (
        <p className="text-caption text-muted-foreground">
          {pt.ask.alreadyRated}
        </p>
      ) : null}
    </div>
  )
}
