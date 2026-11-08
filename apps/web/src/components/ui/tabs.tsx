/**
 * Abas sobre o `Tabs` do Radix, com os papéis `tablist`, `tab` e
 * `tabpanel`.
 *
 * Usadas nas abas Perfil, Conversas e Privacidade de `/account` (seção
 * 15.5) e no `SegmentedStatusCard` do admin. O Radix liga cada aba ao seu
 * painel e move a seleção pelas setas.
 *
 * O projeto trocou o visual do shadcn por uma pílula:
 * - Lista em `--muted`; aba ativa em `--card` com texto `--foreground`,
 *   como o ativo da navegação (seção 14.7). A seção 14.2 cita `--primary`
 *   para a aba ativa; aqui ela usa `--card`.
 * - Aba inativa em `--muted-foreground`, que vira `--foreground` no hover.
 * - 44 px no celular e 32 px no desktop (seção 15.8), `text-body`,
 *   contorno de foco de 2 px e cursor padrão quando desabilitada.
 */
import * as React from "react"
import { cn } from "cn"
import { Tabs as TabsPrimitive } from "radix-ui"

/** Raiz das abas, com `value` (ou `defaultValue`) e `onValueChange`. */
function Tabs({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      className={cn("flex flex-col gap-4", className)}
      {...props}
    />
  )
}

/** A pílula com as abas. Dê o nome do grupo com `aria-label`. */
function TabsList({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(
        "flex w-fit max-w-full flex-wrap items-center gap-1 rounded-full bg-muted p-1",
        className
      )}
      {...props}
    />
  )
}

/**
 * Uma aba. O Radix põe `data-state="active"` na aba escolhida, e as
 * classes `data-[state=active]:` a pintam de `--card`.
 */
function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "inline-flex min-h-11 items-center justify-center rounded-full px-4 text-body text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-default disabled:opacity-50 data-[state=active]:bg-card data-[state=active]:text-foreground md:min-h-8",
        className
      )}
      {...props}
    />
  )
}

/**
 * Painel de uma aba. O Radix o deixa focável (`tabIndex` 0), para quem usa
 * teclado chegar ao conteúdo, e por isso ele também tem o contorno de foco.
 * Por padrão, só o painel ativo fica montado.
 */
function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn(
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        className
      )}
      {...props}
    />
  )
}

export { Tabs, TabsContent, TabsList, TabsTrigger }
