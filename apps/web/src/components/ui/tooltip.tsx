/**
 * Dica flutuante sobre o `Tooltip` do Radix, do shadcn/ui (`radix-nova`).
 *
 * Usada na barra lateral recolhida: cada link mostra o nome à direita
 * (M13). O `TooltipProvider` fica no `SidebarBody`, e não na raiz, para o
 * visitante sem sessão não baixar o código do tooltip (seção 13.1).
 *
 * O que o projeto mudou no gerado pelo shadcn: superfície `--popover` com
 * `text-caption` em `--foreground`, `shadow-overlay` e borda `--border`
 * (seções 14.2 e 14.4), raio `rounded-md` e nenhuma animação de CSS, então
 * a dica aparece direto. A seta usa a cor do fundo.
 */
import * as React from "react"
import { cn } from "cn"
import { Tooltip as TooltipPrimitive } from "radix-ui"

/**
 * Provedor que o Radix exige acima de todo `Tooltip`. Com
 * `delayDuration = 0`, a dica abre sem espera.
 */
function TooltipProvider({
  delayDuration = 0,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Provider>) {
  return (
    <TooltipPrimitive.Provider
      data-slot="tooltip-provider"
      delayDuration={delayDuration}
      {...props}
    />
  )
}

/**
 * Raiz de uma dica. Ela não traz o próprio provedor: sem um
 * `TooltipProvider` acima, o Radix lança erro.
 */
function Tooltip({
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Root>) {
  return <TooltipPrimitive.Root data-slot="tooltip" {...props} />
}

/**
 * Elemento que abre a dica no hover e no foco. Com `asChild`, o próprio
 * link vira o gatilho, e o Radix liga a dica a ele por `aria-describedby`.
 */
function TooltipTrigger({
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Trigger>) {
  return <TooltipPrimitive.Trigger data-slot="tooltip-trigger" {...props} />
}

/** Caixa da dica, em portal, colada no gatilho (`sideOffset` 0). */
function TooltipContent({
  className,
  sideOffset = 0,
  children,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        data-slot="tooltip-content"
        sideOffset={sideOffset}
        className={cn(
          "z-50 inline-flex w-fit max-w-xs origin-(--radix-tooltip-content-transform-origin) items-center gap-1.5 rounded-md bg-popover px-3 py-1.5 text-caption text-foreground shadow-overlay ring-1 ring-border has-data-[slot=kbd]:pr-1.5 **:data-[slot=kbd]:relative **:data-[slot=kbd]:isolate **:data-[slot=kbd]:z-50 **:data-[slot=kbd]:rounded-sm",
          className
        )}
        {...props}
      >
        {children}
        <TooltipPrimitive.Arrow className="z-50 size-2.5 translate-y-[calc(-50%_-_2px)] rotate-45 rounded-[2px] bg-popover fill-popover" />
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  )
}

export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger }
