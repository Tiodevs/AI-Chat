import { useState } from "react"

import { PageHeading } from "@/app/page-heading.tsx"
import { ChatThread } from "@/components/patterns/chat-thread.tsx"
import { Composer } from "@/components/patterns/composer.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import type { Turn } from "@/features/ask/types.ts"
import { pt } from "@/i18n/pt.ts"

import { SuggestionChips } from "./suggestion-chips.tsx"

export function ConversationScreen({
  messages,
  live,
  loading,
  pending,
  streaming,
  error,
  requestId,
  rateLimit,
  budgetExceeded,
  onAsk,
  onStop,
  onFeedback,
}: {
  messages: Turn[]
  live: string
  loading: boolean
  pending: boolean
  streaming: boolean
  error: string | null
  requestId: string | null
  rateLimit: string | null
  budgetExceeded: boolean
  onAsk: (text: string) => void
  onStop: () => void
  onFeedback: (messageId: string, rating: 1 | -1) => void
}) {
  const [value, setValue] = useState("")
  const hasMessages = messages.length > 0

  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-1 flex-col gap-4">
      <PageHeading title={pt.pages.ask} />
      <div className="flex flex-1 flex-col gap-4">
        {loading && !hasMessages ? <LoadingLines /> : null}
        {!loading && !hasMessages ? (
          <SuggestionChips
            disabled={budgetExceeded || streaming || pending}
            onSelect={onAsk}
          />
        ) : null}
        {hasMessages ? (
          <ChatThread
            messages={messages}
            live={live}
            onFeedback={onFeedback}
            onRetry={onAsk}
          />
        ) : null}
        {rateLimit ? (
          <p role="alert" className="text-body text-foreground">
            {rateLimit}
          </p>
        ) : null}
        {error ? (
          <div role="alert" className="flex flex-col gap-3">
            <p className="text-body text-foreground">{error}</p>
            {requestId ? <RequestIdCopy requestId={requestId} /> : null}
          </div>
        ) : null}
      </div>
      <div className="sticky bottom-0 z-10 bg-background pt-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <Composer
          value={value}
          onChange={setValue}
          onSubmit={() => {
            const text = value.trim()
            if (!text) {
              return
            }
            onAsk(text)
            setValue("")
          }}
          onStop={onStop}
          streaming={streaming}
          pending={pending}
          disabled={budgetExceeded}
          disabledReason={budgetExceeded ? pt.ask.unavailable : null}
          error={null}
        />
      </div>
    </div>
  )
}

function LoadingLines() {
  return (
    <div aria-busy="true" className="flex flex-col gap-2">
      <span className="sr-only">{pt.loading}</span>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-4/5" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  )
}
