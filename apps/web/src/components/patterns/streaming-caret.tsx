/**
 * Caret que pisca enquanto a resposta é gerada (seção 14.6).
 *
 * Aparece no `AssistantMessage` (espera e fluxo) e no `AssistantBubble`
 * do cadastro, enquanto o assistente escreve.
 *
 * Movimento: M7 (seção 16.3), o preset `pulseCaret`, com a opacidade
 * entre 1 e 0,3 em laço (`repeat: -1`, `yoyo`) a cada 0,6 s. É o único
 * laço da interface, porque indica atividade (seção 16.1). Com movimento
 * reduzido, o caret fica parado. Ele some no `done` porque o pai deixa de
 * renderizá-lo, e o `useGSAP` desfaz o laço ao desmontar.
 *
 * Acessibilidade: `aria-hidden`, só visual. Quem diz ao leitor de tela que
 * a resposta está chegando é o `aria-busy` do pai.
 */
import { useRef } from "react"

import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

/** Traço vertical de 1em de altura, na cor do texto. */
export function StreamingCaret() {
  const ref = useRef<HTMLSpanElement>(null)
  const { reduced } = useMotion()

  useGSAP(
    () => {
      presets.pulseCaret(ref.current, reduced)
    },
    { scope: ref }
  )

  return (
    <span
      ref={ref}
      data-caret
      aria-hidden="true"
      className="ms-0.5 inline-block h-[1em] w-0.5 bg-foreground align-middle"
    />
  )
}
