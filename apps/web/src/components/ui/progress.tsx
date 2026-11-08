/**
 * Barra de progresso sobre o `Progress` do Radix, do shadcn/ui.
 *
 * Usada no card de orçamento diário de tokens em `/admin`, que pinta o
 * indicador de `--warning` a partir de 80% (seção 15.5). O Radix põe
 * `role="progressbar"`, `aria-valuemin`, `aria-valuemax` e
 * `aria-valuenow`; o chamador dá o nome com `aria-label`.
 *
 * O indicador ocupa a largura toda e recua com `translateX`: só
 * `transform` muda, nunca a largura (seção 16.1). A `transition-all` é
 * uma transição de CSS fora do catálogo da seção 16.3; com movimento
 * reduzido, os estilos globais de `globals.css` a zeram. O `"use client"`
 * veio do modelo do shadcn e não tem efeito numa SPA do Vite.
 */
"use client"

import * as React from "react"
import { cn } from "cn"
import { Progress as ProgressPrimitive } from "radix-ui"

/** Barra com `value` de 0 a 100. Sem valor, o indicador fica recuado. */
function Progress({
  className,
  value,
  ...props
}: React.ComponentProps<typeof ProgressPrimitive.Root>) {
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      className={cn(
        "relative flex h-1 w-full items-center overflow-x-hidden rounded-full bg-muted",
        className
      )}
      {...props}
    >
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className="size-full flex-1 bg-primary transition-all"
        style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
      />
    </ProgressPrimitive.Root>
  )
}

export { Progress }
