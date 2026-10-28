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

export function RegistrationStepper({ phase }: { phase: RegistrationPhase }) {
  const rootRef = useRef<HTMLDivElement>(null)
  const barRef = useRef<HTMLDivElement>(null)
  const { reduced } = useMotion()
  const scale = phaseScale(phase)
  const currentIndex = registrationPhases.indexOf(phase)

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
