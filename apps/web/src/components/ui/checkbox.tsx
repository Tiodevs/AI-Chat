/**
 * Caixa de seleção sobre o `Checkbox` do Radix, que renderiza um `button`
 * com `role="checkbox"` e `aria-checked`.
 *
 * Usada só nos aceites do `ConsentFieldSet`, nos dois cadastros
 * (`/register` e `/register/form`).
 *
 * O projeto trocou o visual do shadcn:
 * - 24 px (`size-6`), o alvo mínimo de desktop da seção 15.8. No
 *   `ConsentFieldSet`, o rótulo chega a 44 px no celular e também marca a
 *   caixa, pelo `htmlFor`.
 * - Borda `--border-strong`, a dos controles, e fundo `--card` (14.2).
 * - Borda `--danger` com `aria-invalid` e cursor padrão quando desabilitada
 *   (seção 14.7).
 * - Sem anel de foco próprio: vale o contorno global de 2 px.
 *
 * Marcada, ela vira `--primary` com o visto em `--primary-foreground`, a
 * seleção invertida da seção 14.1. As classes `data-[state=checked]:` leem
 * o `data-state` que o Radix põe no elemento. Seção 14.6.
 */
import * as React from "react"
import { cn } from "cn"
import { CheckIcon } from "lucide-react"
import { Checkbox as CheckboxPrimitive } from "radix-ui"

/**
 * Caixa controlada pelo Radix: `checked` e `onCheckedChange`, que entrega
 * `true`, `false` ou `"indeterminate"`. O `Indicator` só monta o visto
 * quando a caixa está marcada.
 */
function Checkbox({
  className,
  ...props
}: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer size-6 shrink-0 rounded-md border border-border-strong bg-card text-primary-foreground disabled:cursor-default disabled:opacity-50 aria-invalid:border-danger data-[state=checked]:border-primary data-[state=checked]:bg-primary",
        className
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className="grid place-content-center text-current"
      >
        <CheckIcon className="size-3.5" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
