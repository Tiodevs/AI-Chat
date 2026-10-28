import { AssistantMessage } from "@/components/patterns/assistant-message.tsx"
import { UserMessage } from "@/components/patterns/user-message.tsx"
import type { Turn } from "@/features/ask/types.ts"
import { pt } from "@/i18n/pt.ts"

export function ChatThread({
  messages,
  live,
  onFeedback,
  onRetry,
}: {
  messages: Turn[]
  live: string
  onFeedback: (messageId: string, rating: 1 | -1) => void
  onRetry: (text: string) => void
}) {
  return (
    <div className="flex flex-col gap-4" aria-label={pt.ask.thread}>
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {live}
      </div>
      <ol className="m-0 flex list-none flex-col gap-4 p-0">
        {messages.map((message) => (
          <li key={message.key}>
            {message.role === "user" ? (
              <UserMessage text={message.text} privacy={message.privacy} />
            ) : (
              <AssistantMessage
                phase={message.phase}
                text={message.text}
                outgoing={message.outgoing}
                citations={message.citations}
                outcome={message.outcome}
                replaced={message.replaced}
                errorMessage={message.errorMessage}
                requestId={message.requestId}
                feedback={message.feedback}
                canAnswer={message.phase === "done" && message.id !== null}
                onFeedback={(rating) => {
                  if (message.id) {
                    onFeedback(message.id, rating)
                  }
                }}
                onRetry={() => {
                  if (message.retryText) {
                    onRetry(message.retryText)
                  }
                }}
              />
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
