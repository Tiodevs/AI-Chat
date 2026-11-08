/**
 * Balão da pergunta do visitante, à direita, em `--card` (seção 14.6).
 *
 * Aparece no `ChatThread` da conversa (`/ask/:id?`) e na transcrição do
 * cadastro por conversa (`/register`).
 *
 * Privacidade (seção 15.5, recusa médica): quando a resposta seguinte foi
 * uma recusa, o store marca `privacy` e o balão mostra só a nota "Para
 * proteger sua privacidade, não guardamos esta mensagem." no lugar do
 * texto. Quem decide é `syncPrivacy`, em `features/ask/model.ts`.
 *
 * Movimento: M5 (seção 16.3), o preset `enterUserMessage`, com
 * `autoAlpha` e `y` de 6 a 0 ao montar. Com movimento reduzido, o preset
 * mostra o balão direto. Usa `text-message` (15/24), a tipografia de
 * leitura das mensagens (seção 14.3).
 */
import { useRef } from "react"

import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

/** Balão de uma pergunta. */
export function UserMessage({
  text,
  privacy,
}: {
  text: string
  /** Troca o texto pela nota de privacidade da recusa médica. */
  privacy: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  const { reduced } = useMotion()

  // `useGSAP` roda depois da montagem, dentro de um contexto do GSAP, e
  // desfaz as animações ao desmontar. O `scope` limita seletores em texto
  // à subárvore da ref (seção 16.5). Sem dependências, roda uma vez.
  useGSAP(
    () => {
      presets.enterUserMessage(ref.current, reduced)
    },
    { scope: ref }
  )

  return (
    <div ref={ref} className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl bg-card px-4 py-3 text-message text-foreground">
        <p className="whitespace-pre-wrap">
          {privacy ? pt.ask.privacyNote : text}
        </p>
      </div>
    </div>
  )
}
