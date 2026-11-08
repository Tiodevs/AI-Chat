/**
 * O registro único do GSAP no app (seção 16.2).
 *
 * Registra o `useGSAP` e define os padrões globais: duração
 * `duration.base` e curva `ease.enter`, de `tokens.ts`. Quem anima importa
 * `gsap` e `useGSAP` daqui, e não dos pacotes: assim o registro roda antes
 * da primeira animação. O Flip fica de fora, em `flip.ts`, que só a barra
 * lateral carrega (seção 5.3).
 *
 * O `useGSAP`, de `@gsap/react`, é um `useLayoutEffect` que cria um
 * contexto do GSAP. Com `scope` numa ref, os seletores só procuram dentro
 * dela, e as animações criadas ali são desfeitas quando o componente sai
 * da tela (seção 16.5).
 *
 * Quem usa: `MotionProvider.tsx`, `presets.ts`, `flip.ts`,
 * `useGsapPresence.ts`, a casca (`app/shell.tsx`) e os componentes de
 * `components/patterns` que animam.
 */
import { useGSAP } from "@gsap/react"
import gsap from "gsap"

import { motionTokens } from "./tokens.ts"

gsap.registerPlugin(useGSAP)
// Vale para todo tween que não diga a própria duração ou curva.
gsap.defaults({
  duration: motionTokens.duration.base,
  ease: motionTokens.ease.enter,
})

export { gsap, useGSAP }
