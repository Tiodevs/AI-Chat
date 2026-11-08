/**
 * Grupo de botões alternáveis sobre o `ToggleGroup` do Radix. É o chip da
 * interface.
 *
 * Aparece nas sugestões do início (seção 15.5), no período do
 * `TrendChartCard`, nos filtros de período e de feedback de
 * `/admin/quality`, no status do pedido em `/admin/privacy`, no tipo de
 * pedido em `/privacy`, na preferência de movimento e nos campos de
 * escolha de `/account` e `/register/form`, e nas opções do
 * `ProfileSummaryCard`.
 *
 * O projeto trocou o modelo do shadcn, que monta o item com o `Toggle` e
 * repassa variantes por contexto, por um chip fixo:
 * - Pílula com borda `--border-strong`, fundo `--card` e hover `--muted`
 *   (seção 14.7).
 * - Ligado em `--primary` com `--primary-foreground`, a seleção forte da
 *   seção 14.7.
 * - 44 px no celular e 32 px no desktop (seção 15.8), contorno de foco de
 *   2 px e cursor padrão quando desabilitado.
 */
import * as React from "react"
import { cn } from "cn"
import { ToggleGroup as ToggleGroupPrimitive } from "radix-ui"

/**
 * Raiz do grupo. Com `type="single"`, o Radix dá ao grupo o papel
 * `radiogroup`, e a cada item o papel `radio` com `aria-checked`; com
 * `type="multiple"`, o grupo vira `toolbar`, com itens `aria-pressed`.
 * Dê o nome com `aria-label` ou `aria-labelledby`.
 */
function ToggleGroup({
  className,
  ...props
}: React.ComponentProps<typeof ToggleGroupPrimitive.Root>) {
  return (
    <ToggleGroupPrimitive.Root
      data-slot="toggle-group"
      className={cn("flex flex-wrap items-center gap-2", className)}
      {...props}
    />
  )
}

/**
 * Um chip. O Radix põe `data-state="on"` no item ligado, e as classes
 * `data-[state=on]:` o pintam de `--primary`.
 */
function ToggleGroupItem({
  className,
  ...props
}: React.ComponentProps<typeof ToggleGroupPrimitive.Item>) {
  return (
    <ToggleGroupPrimitive.Item
      data-slot="toggle-group-item"
      className={cn(
        "inline-flex min-h-11 items-center justify-center rounded-full border border-border-strong bg-card px-4 text-body text-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-default disabled:opacity-50 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground md:min-h-8",
        className
      )}
      {...props}
    />
  )
}

export { ToggleGroup, ToggleGroupItem }
