/**
 * Linha divisória sobre o `Separator` do Radix, do shadcn/ui, sem mudança.
 *
 * Usada na barra lateral (`SidebarBody`) e no `FieldSeparator`. A cor é
 * `--border` (seção 14.2). Por padrão é decorativa: o Radix põe
 * `role="none"`, e o leitor de tela a ignora. Com `decorative={false}`,
 * ela vira `role="separator"`.
 *
 * `data-horizontal:` e `data-vertical:` são variantes do
 * `shadcn/tailwind.css` que leem o `data-orientation` do Radix.
 */
import * as React from "react"
import { cn } from "cn"
import { Separator as SeparatorPrimitive } from "radix-ui"

/** Linha de 1 px, horizontal (padrão) ou vertical (`orientation`). */
function Separator({
  className,
  orientation = "horizontal",
  decorative = true,
  ...props
}: React.ComponentProps<typeof SeparatorPrimitive.Root>) {
  return (
    <SeparatorPrimitive.Root
      data-slot="separator"
      decorative={decorative}
      orientation={orientation}
      className={cn(
        "shrink-0 bg-border data-horizontal:h-px data-horizontal:w-full data-vertical:w-px data-vertical:self-stretch",
        className
      )}
      {...props}
    />
  )
}

export { Separator }
