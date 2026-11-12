/**
 * O bloco de um atendimento humano na thread da conversa (seção 29.11).
 *
 * View: recebe o atendimento de `handoff-store.ts` pela tela da conversa e
 * não chama a API. Mostra o divisor de início, as mensagens do visitante
 * (`UserMessage`) e da equipe (`AttendantMessage`) e, encerrado, o divisor
 * com o texto do motivo (seção 29.5) e "Você pode continuar perguntando ao
 * Atrium.". A mensagem nova da equipe chega inteira numa região
 * `aria-live="polite"` (seção 29.11).
 */
import {
  removedText,
  AttendantMessage,
} from "@/components/patterns/attendant-message.tsx"
import { UserMessage } from "@/components/patterns/user-message.tsx"
import { Separator } from "@/components/ui/separator.tsx"
import { pt } from "@/i18n/pt.ts"

import type { HandoffView } from "./handoff-store.ts"

/** O texto do divisor de encerramento pelo motivo da seção 29.5. */
export function closeText(reason: string | null): string {
  const reasons: Record<string, string> = pt.handoff.closeReasons
  return (
    (reason ? reasons[reason] : undefined) ?? pt.handoff.closeReasons.resolved
  )
}

/** O atendimento com as mensagens, em ordem, e os divisores. */
export function HandoffBlock({
  handoff,
}: {
  handoff: HandoffView | undefined
}) {
  if (!handoff) {
    return null
  }
  const lastFromTeam = [...handoff.messages]
    .reverse()
    .find((message) => message.role === "attendant")
  return (
    <section aria-label={pt.handoff.started} className="flex flex-col gap-4">
      <Divider text={pt.handoff.started} />
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {lastFromTeam
          ? `${pt.handoff.teamLabel}: ${removedText(lastFromTeam.redaction) ?? lastFromTeam.content}`
          : ""}
      </div>
      <ol className="m-0 flex list-none flex-col gap-4 p-0">
        {handoff.messages.map((message) => (
          <li key={message.id}>
            {message.role === "attendant" ? (
              <AttendantMessage
                text={message.content}
                redaction={message.redaction}
              />
            ) : (
              <UserMessage
                text={removedText(message.redaction) ?? message.content}
                privacy={false}
              />
            )}
          </li>
        ))}
      </ol>
      {handoff.status === "closed" ? (
        <div className="flex flex-col gap-1">
          <Divider text={closeText(handoff.closeReason)} />
          <p className="text-center text-caption text-muted-foreground">
            {pt.handoff.continueWithAtrium}
          </p>
        </div>
      ) : null}
    </section>
  )
}

/** Uma linha com o texto no meio, para marcar o começo e o fim. */
function Divider({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3">
      <Separator className="flex-1" />
      <span className="max-w-[80%] text-center text-caption text-muted-foreground">
        {text}
      </span>
      <Separator className="flex-1" />
    </div>
  )
}
