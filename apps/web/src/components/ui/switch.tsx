/**
 * Interruptor sobre o `Switch` do Radix, que renderiza um `button` com
 * `role="switch"` e `aria-checked`.
 *
 * Usado nos consentimentos opcionais da aba Privacidade de `/account`
 * (seção 15.5), um por aceite, com a data em que ele foi dado.
 *
 * O projeto trocou o visual do shadcn:
 * - 24 por 44 px, que cumpre o alvo de 24 px do desktop (seção 15.8). No
 *   celular, o `FieldLabel` da conta chega a 44 px de altura.
 * - Borda `--border-strong` e fundo `--card`; borda `--danger` com
 *   `aria-invalid`.
 * - Ligado em `--primary` com o polegar em `--primary-foreground`, a
 *   seleção invertida da seção 14.1.
 * - Contorno de foco explícito de 2 px com 2 px de afastamento e cursor
 *   padrão quando desabilitado (seção 14.7).
 *
 * O polegar muda de lado com `translate-x` pelo `data-state` do Radix, sem
 * transição: troca direto. Seção 14.6.
 */
import * as React from "react"
import { cn } from "cn"
import { Switch as SwitchPrimitive } from "radix-ui"

/** Interruptor controlado por `checked` e `onCheckedChange`. */
function Switch({
  className,
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn(
        "peer inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-border-strong bg-card focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-default disabled:opacity-50 aria-invalid:border-danger data-[state=checked]:border-primary data-[state=checked]:bg-primary",
        className
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className="block size-4 translate-x-1 rounded-full bg-foreground data-[state=checked]:translate-x-6 data-[state=checked]:bg-primary-foreground"
      />
    </SwitchPrimitive.Root>
  )
}

export { Switch }
