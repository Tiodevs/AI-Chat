/**
 * Rota `/ask/:id?`, a conversa: pergunta, resposta em fluxo, fontes e
 * feedback (seções 7.1 e 15.5).
 *
 * Liga o controller `useAskConversation` à tela `ConversationScreen` (SDD
 * 13.2). O `id` vem da URL. Sem ele, em `/ask`, a primeira pergunta cria a
 * conversa e leva a `/ask/:id`, como no início. O estado da conversa fica
 * em `features/ask/store.ts`, e não no cache do TanStack Query.
 */
import { useParams } from "react-router"

import { ConversationScreen } from "@/features/ask/conversation-screen.tsx"
import { useAskConversation } from "@/features/ask/useAskConversation.ts"

/** Passa à tela o estado da conversa e as ações de perguntar e parar. */
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
