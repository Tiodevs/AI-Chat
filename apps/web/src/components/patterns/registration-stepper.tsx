/**
 * Indicador das etapas do cadastro: Dados, Senha, Revisão e Aceite, com
 * uma barra de progresso (seção 14.6).
 *
 * Fora das telas desde 2026-11-04: o cadastro por conversa não tem mais
 * indicador de etapas (seção 15.5). O componente fica no Storybook.
 *
 * Acessibilidade: uma lista ordenada com nome, e `aria-current="step"`
 * na etapa atual. A etapa atual fica em `--primary` (seleção forte, seção
 * 14.7). A barra é `aria-hidden`: a lista já diz onde a pessoa está.
 *
 * Movimento: M11 (seção 16.3), o preset `moveStepper`, que leva a barra
 * ao `scaleX` da etapa com `ease.move`, sem animar a largura. Com
 * movimento reduzido, a barra muda direto.
 */
import { useRef } from "react"

import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"
import { cn } from "@/lib/utils.ts"
import {
  phaseScale,
  registrationPhases,
  type RegistrationPhase,
} from "@/features/registration/model.ts"

/** As quatro etapas e a barra, na fase dada. */
export function RegistrationStepper({ phase }: { phase: RegistrationPhase }) {
  const rootRef = useRef<HTMLDivElement>(null)
  const barRef = useRef<HTMLDivElement>(null)
  const { reduced } = useMotion()
  // Fração de 1/4 a 1: a etapa atual conta como andada.
  const scale = phaseScale(phase)
  const currentIndex = registrationPhases.indexOf(phase)

  // Começa em `scale-x-0` pela classe e anima até `scale` a cada etapa.
  useGSAP(
    () => {
      presets.moveStepper(barRef.current, reduced, scale)
    },
    { scope: rootRef, dependencies: [scale, reduced] }
  )

  return (
    <div ref={rootRef} className="flex flex-col gap-3">
      <ol aria-label={pt.registration.stepsLabel} className="flex gap-2">
        {registrationPhases.map((item, index) => {
          const current = item === phase
          const done = index < currentIndex
          return (
            <li
              key={item}
              aria-current={current ? "step" : undefined}
              className={cn(
                "flex min-h-11 flex-1 items-center rounded-lg border px-3 text-label md:min-h-8",
                current && "border-primary bg-primary text-primary-foreground",
                done && "border-border bg-card text-foreground",
                !current &&
                  !done &&
                  "border-border bg-card text-muted-foreground"
              )}
            >
              {pt.registration.steps[item]}
            </li>
          )
        })}
      </ol>
      <div
        className="h-1 overflow-hidden rounded-full bg-muted"
        aria-hidden="true"
      >
        <div
          ref={barRef}
          className="h-full w-full origin-left scale-x-0 bg-primary"
        />
      </div>
    </div>
  )
}
