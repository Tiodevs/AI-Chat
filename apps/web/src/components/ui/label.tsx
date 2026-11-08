/**
 * Rótulo sobre o `Label` do Radix, do shadcn/ui, sem mudança de classe.
 *
 * O `Label` do Radix renderiza um `<label>`. Com `htmlFor`, clicar no
 * rótulo foca ou marca o controle, e o texto vira o nome acessível dele.
 * É a base do `FieldLabel` e o rótulo das caixas do `ConsentFieldSet`.
 *
 * `peer-disabled:` e `group-data-[disabled=true]:` esmaecem o rótulo
 * quando o controle irmão ou o `Field` pai estão desabilitados. Seção
 * 14.6.
 */
import * as React from "react"
import { cn } from "cn"
import { Label as LabelPrimitive } from "radix-ui"

/** Rótulo de um controle. Ligue-o com `htmlFor` ao `id` do controle. */
function Label({
  className,
  ...props
}: React.ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      data-slot="label"
      className={cn(
        "flex items-center gap-2 text-sm leading-none font-medium select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Label }
