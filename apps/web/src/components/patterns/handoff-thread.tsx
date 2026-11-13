/**
 * A conversa de um atendimento para quem o assumiu, ou para o admin que
 * abriu um encerrado (seções 29.9.4 e 29.11).
 *
 * Duas partes: a conversa com o Atrium, com as perguntas, as respostas, as
 * fontes e o selo do desfecho, e as mensagens do atendimento. Nunca nome,
 * e-mail, telefone ou tipo de visitante: a API não os manda. Todo texto
 * sai como texto puro, com `white-space: pre-wrap`: um link não vira
 * elemento clicável (seção 29.8). A mensagem de saúde da conversa com a IA
 * já vem gravada como o marcador e aparece só como o aviso.
 *
 * Cada mensagem do atendimento tem a ação Remover conteúdo, que sobe por
 * `onRedact`; com `readOnly`, a ação some.
 *
 * No canal WhatsApp (seção 30.5), a mensagem da equipe mostra o status de
 * entrega em texto pequeno: Enviando, Enviada, Entregue, Lida ou Não
 * entregue com o motivo. Só a falha é anunciada ao leitor de tela.
 */
import { useId } from "react"

import {
  OutcomeBadge,
  type OutcomeKind,
} from "@/components/patterns/outcome-badge.tsx"
import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

/** O marcador gravado no lugar de uma pergunta de saúde (seção 11.4). */
const healthMarker = "[health-related message not stored]"

/** Uma mensagem da conversa com a IA. */
export type ThreadLine = {
  id: string
  role: "user" | "assistant"
  content: string
  citations: { index: number; documentTitle: string; heading: string | null }[]
  outcome: string | null
}

/** Uma mensagem do atendimento. */
export type ThreadMessage = {
  id: string
  role: "user" | "attendant"
  content: string
  redaction: string | null
  /** O status de entrega no WhatsApp, só na mensagem da equipe (seção 30.5). */
  delivery?: DeliveryStatus | null
  deliveryError?: string | null
}

/** Os status de entrega do WhatsApp, na ordem em que acontecem. */
export type DeliveryStatus =
  "pending" | "sent" | "delivered" | "read" | "failed"

/** O texto do status de entrega, com o motivo quando falhou. */
export function deliveryText(
  delivery: DeliveryStatus,
  error: string | null | undefined
): string {
  const label = pt.attendance.delivery[delivery]
  return delivery === "failed" && error ? `${label}: ${error}` : label
}

/** O selo de cada desfecho da seção 7.1, quando ele tem selo. */
function outcomeKind(outcome: string | null): OutcomeKind | null {
  if (
    outcome === "answered" ||
    outcome === "abstained" ||
    outcome === "refused"
  ) {
    return outcome
  }
  if (outcome === "grounding_failed") {
    return "replaced"
  }
  if (outcome === "off_topic") {
    return "abstained"
  }
  if (outcome === "degraded" || outcome === "error") {
    return "unavailable"
  }
  return null
}

/** O texto de uma mensagem removida, com a categoria. */
function removedText(redaction: string): string {
  const categories: Record<string, string> = pt.attendance.categories
  return pt.attendance.removedMessage.replace(
    "{category}",
    categories[redaction] ?? redaction
  )
}

/** A conversa e as mensagens do atendimento. */
export function HandoffThread({
  conversation,
  messages,
  readOnly = false,
  onRedact,
}: {
  conversation: ThreadLine[]
  messages: ThreadMessage[]
  readOnly?: boolean
  onRedact?: (messageId: string) => void
}) {
  const conversationId = useId()
  const handoffId = useId()
  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby={conversationId} className="flex flex-col gap-3">
        <h3 id={conversationId} className="text-label text-foreground-strong">
          {pt.attendance.conversationTitle}
        </h3>
        <ol className="m-0 flex list-none flex-col gap-3 p-0">
          {conversation.map((line) => {
            const kind =
              line.role === "assistant" ? outcomeKind(line.outcome) : null
            return (
              <li
                key={line.id}
                className="flex flex-col gap-1.5 rounded-lg bg-muted px-3 py-2.5"
              >
                <span className="text-caption text-muted-foreground">
                  {line.role === "assistant"
                    ? pt.attendance.atriumLabel
                    : pt.attendance.visitorLabel}
                </span>
                <p className="text-body break-words whitespace-pre-wrap text-foreground">
                  {line.content === healthMarker
                    ? pt.attendance.healthMarker
                    : line.content}
                </p>
                {kind ? <OutcomeBadge kind={kind} /> : null}
                {line.citations.length > 0 ? (
                  <p className="text-caption text-muted-foreground">
                    {pt.ask.sources}:{" "}
                    {line.citations
                      .map((citation) =>
                        citation.heading
                          ? `${citation.documentTitle}, ${citation.heading}`
                          : citation.documentTitle
                      )
                      .join("; ")}
                  </p>
                ) : null}
              </li>
            )
          })}
        </ol>
      </section>
      <section aria-labelledby={handoffId} className="flex flex-col gap-3">
        <h3 id={handoffId} className="text-label text-foreground-strong">
          {pt.attendance.handoffTitle}
        </h3>
        <ol className="m-0 flex list-none flex-col gap-3 p-0">
          {messages.map((message) => (
            <li
              key={message.id}
              className={
                message.role === "attendant"
                  ? "flex flex-col gap-1.5 rounded-lg bg-card px-3 py-2.5 ring-1 ring-foreground/10"
                  : "flex flex-col gap-1.5 rounded-lg bg-muted px-3 py-2.5"
              }
            >
              <span className="text-caption text-muted-foreground">
                {message.role === "attendant"
                  ? pt.attendance.teamLabel
                  : pt.attendance.visitorLabel}
              </span>
              <p
                className={
                  message.redaction
                    ? "text-body text-muted-foreground italic"
                    : "text-body break-words whitespace-pre-wrap text-foreground"
                }
              >
                {message.redaction
                  ? removedText(message.redaction)
                  : message.content}
              </p>
              {message.role === "attendant" && message.delivery ? (
                <span
                  className={
                    message.delivery === "failed"
                      ? "text-caption text-destructive"
                      : "text-caption text-muted-foreground"
                  }
                  aria-live={message.delivery === "failed" ? "polite" : "off"}
                >
                  {deliveryText(message.delivery, message.deliveryError)}
                </span>
              ) : null}
              {!readOnly && !message.redaction && onRedact ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="w-fit"
                  onClick={() => {
                    onRedact(message.id)
                  }}
                >
                  {pt.attendance.redact}
                </Button>
              ) : null}
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
