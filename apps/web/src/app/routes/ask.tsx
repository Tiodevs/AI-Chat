import { useParams } from "react-router"

import { ConversationScreen } from "@/features/ask/conversation-screen.tsx"
import { useAskConversation } from "@/features/ask/useAskConversation.ts"

export function Component() {
  const { id } = useParams()
  const ask = useAskConversation(id)
  return (
    <ConversationScreen
      messages={ask.messages}
      live={ask.live}
      loading={ask.loading}
      pending={ask.pending}
      streaming={ask.streaming}
      error={ask.error}
      requestId={ask.requestId}
      rateLimit={ask.rateLimit}
      budgetExceeded={ask.budgetExceeded}
      onAsk={ask.ask}
      onStop={ask.stop}
      onFeedback={ask.feedback}
    />
  )
}
