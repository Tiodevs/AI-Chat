/**
 * Mensagem da equipe no atendimento humano, à esquerda, com o rótulo
 * "Equipe do Harborlight" e o ícone `Headset` (seções 29.9.5 e 29.11).
 *
 * Aparece no bloco do atendimento da conversa (`features/ask`). É diferente
 * do `AssistantMessage` de propósito: o visitante sempre sabe se quem
 * responde é a IA ou uma pessoa. O texto sai como texto puro, com
 * `white-space: pre-wrap`: sem Markdown, sem HTML e sem link clicável
 * (seção 29.8). Uma mensagem removida mostra o aviso no lugar do texto.
 *
 * Movimento: o preset do M5 ao chegar (`enterAttendantMessage`, seção
 * 29.11), direto com movimento reduzido.
 */
import { Headset } from "lucide-react"
import { useRef } from "react"

import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

/** Balão de uma mensagem da equipe. */
export function AttendantMessage({
  text,
  redaction,
}: {
  text: string
  /** A categoria da remoção, `retention`, ou `null` com o texto original. */
  redaction: string | null
}) {
  const ref = useRef<HTMLDivElement>(null)
  const { reduced } = useMotion()
  useGSAP(
    () => {
      presets.enterAttendantMessage(ref.current, reduced)
    },
    { scope: ref }
  )
  const removed = redaction !== null
  return (
    <div ref={ref} className="flex justify-start">
      <div className="flex max-w-[85%] flex-col gap-1.5 rounded-2xl bg-muted px-4 py-3 ring-1 ring-foreground/10">
        <span className="flex items-center gap-2 text-caption text-muted-foreground">
          <Headset aria-hidden="true" className="size-4" />
          {pt.handoff.teamLabel}
        </span>
        <p
          className={
            removed
              ? "text-message whitespace-pre-wrap text-muted-foreground italic"
              : "text-message whitespace-pre-wrap text-foreground"
          }
        >
          {removedText(redaction) ?? text}
        </p>
      </div>
    </div>
  )
}

/**
 * O aviso no lugar de uma mensagem removida: pela equipe, o texto da seção
 * 29.9.6; pela retenção de 90 dias, o da seção 29.9.9. Sem remoção, `null`.
 */
export function removedText(redaction: string | null): string | null {
  if (redaction === null) {
    return null
  }
  return redaction === "retention" ? pt.handoff.purged : pt.handoff.removed
}
