/**
 * Tela `/ask/:id`: ler a resposta e conferir a fonte. Seção 15.5 do SDD
 * (Conversa).
 *
 * View: recebe de `app/routes/ask.tsx` o retrato e as ações de
 * `useAskConversation` e não chama a API. A thread é o `ChatThread`, e cada
 * resposta é um `AssistantMessage`, que escolhe o estado da seção 15.5 pela
 * fase do turno. Usa ainda `Composer`, `RequestIdCopy` e, na conversa
 * vazia, as `SuggestionChips` desta pasta.
 */
import { useState } from "react"

import { PageHeading } from "@/app/page-heading.tsx"
import { ChatThread } from "@/components/patterns/chat-thread.tsx"
import { Composer } from "@/components/patterns/composer.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import type { Turn } from "@/features/ask/types.ts"
import { pt } from "@/i18n/pt.ts"

import { SuggestionChips } from "./suggestion-chips.tsx"

/**
 * Coluna de até 760 px com a thread e o compositor fixo embaixo (seção
 * 14.5).
 *
 * - Lendo a conversa, ainda sem mensagens: três linhas de skeleton.
 * - Conversa vazia: as sugestões do início (seção 15.5, estado Vazio).
 * - Com mensagens: o `ChatThread`. Tentar de novo chama `onAsk` com a
 *   pergunta guardada no turno e acrescenta outro turno; a Etapa 14.2 faz
 *   o novo substituir o que falhou.
 * - O limite de taxa e o erro da conversa ficam abaixo, como alerta.
 *
 * Durante a resposta, o `Composer` desabilita o campo e mostra Stop. A
 * Etapa 14.3 troca o `disabled` por `readOnly`, para o foco não sair dele.
 */
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
      {/* Fixo embaixo, com folga para a área segura do celular (seção
          14.5). */}
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
            // O campo é limpo antes de saber se o envio deu certo. A Etapa
            // 14.2 só limpa depois do envio aceito.
            setValue("")
          }}
          onStop={onStop}
          streaming={streaming}
          pending={pending}
          disabled={budgetExceeded}
          disabledReason={budgetExceeded ? pt.ask.unavailable : null}
          // Os erros da conversa ficam no alerta acima, não no campo.
          error={null}
        />
      </div>
    </div>
  )
}

/**
 * Skeleton da conversa sendo lida. O `aria-busy` e o texto escondido avisam
 * o leitor de tela de que a página carrega.
 */
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
