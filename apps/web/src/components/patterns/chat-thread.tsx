/**
 * Fio da conversa: a lista de turnos de `/ask/:id?` (seção 15.5), com a
 * região que anuncia a resposta ao leitor de tela.
 *
 * Recebe os turnos prontos do store da conversa (`features/ask`) e
 * escolhe o balão: `UserMessage` à direita, `AssistantMessage` à esquerda,
 * sem balão. Não chama a API: avaliação e nova tentativa sobem por
 * callback para o `useAskConversation` (seção 13.2).
 *
 * Acessibilidade (seção 15.8): uma região `aria-live="polite"`, escondida
 * com `sr-only`, lê o texto de `live`. O store só troca esse texto quando
 * a resposta termina (`announcementFor`, em `features/ask/model.ts`), então
 * o leitor de tela ouve a resposta inteira uma vez, e não token a token.
 * Seções 14.6 e 15.8.
 */
import { AssistantMessage } from "@/components/patterns/assistant-message.tsx"
import { UserMessage } from "@/components/patterns/user-message.tsx"
import type { Turn } from "@/features/ask/types.ts"
import { pt } from "@/i18n/pt.ts"

/** Lista de mensagens com a região de anúncio. */
export function ChatThread({
  messages,
  live,
  onFeedback,
  onRetry,
}: {
  messages: Turn[]
  /**
   * Texto que o leitor de tela anuncia: a resposta completa no `done`, ou
   * a mensagem de erro ou de interrupção. Durante a geração, o store não o
   * troca, e nada é anunciado.
   */
  live: string
  /** Avaliação de uma resposta já gravada, pelo id da mensagem. */
  onFeedback: (messageId: string, rating: 1 | -1) => void
  /** Manda de novo a pergunta que originou o turno que falhou. */
  onRetry: (text: string) => void
}) {
  // O `aria-label` num `div` sem papel não cria uma região nomeada. A
  // Etapa 14.3 do plano põe `role="log"` na conversa.
  return (
    <div className="flex flex-col gap-4" aria-label={pt.ask.thread}>
      {/* `aria-atomic`: o leitor relê a região inteira a cada mudança. */}
      {/* Um texto igual ao anterior não muda a região e não é relido; a */}
      {/* Etapa 14.3 corrige o erro repetido que não se anuncia de novo. */}
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
                // As ações de avaliar e copiar só valem para uma resposta
                // concluída e gravada: sem o id da mensagem (evento
                // `meta`), não há o que avaliar.
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
