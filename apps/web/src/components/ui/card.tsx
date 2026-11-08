/**
 * Superfície de card do shadcn/ui (`radix-nova`): `div`s com classes, sem
 * primitivo do Radix.
 *
 * É a base dos cartões do admin em `/admin` (`StatCard`, `TrendChartCard`,
 * `SegmentedStatusCard`, `GroupedBarCard` e o card de orçamento), do envio
 * de documento em `/admin/documents`, do `SidebarNoticeCard` e da página
 * `/sign-in`.
 *
 * Fundo `bg-card` (`--card`) e borda por `ring-1`, sem sombra: na
 * referência, as superfícies se separam por luminosidade (seções 14.1 e
 * 14.4). A variável `--card-spacing` (16 px, ou 12 px com `size="sm"`)
 * dá o espaço de todas as partes.
 *
 * Diferença da seção 14.4: o raio padrão é `rounded-xl` (cerca de 11 px)
 * e a borda é `--foreground` a 10%. O raio de 16 px e a borda `--border`
 * só entram onde o chamador passa `rounded-card` e `ring-border`, como no
 * `SidebarNoticeCard`. Seção 14.6.
 */
import * as React from "react"
import { cn } from "cn"

/**
 * Contêiner do card. `size="sm"` reduz o espaçamento. Os seletores
 * `has-data-[slot=...]` acertam o padding quando há rodapé ou imagem no
 * topo. Recebe `ref` como prop (React 19), que o `StatCard` e o
 * `TrendChartCard` usam como escopo do GSAP.
 */
function Card({
  className,
  size = "default",
  ...props
}: React.ComponentProps<"div"> & { size?: "default" | "sm" }) {
  return (
    <div
      data-slot="card"
      data-size={size}
      className={cn(
        "group/card flex flex-col gap-(--card-spacing) overflow-hidden rounded-xl bg-card py-(--card-spacing) text-sm text-card-foreground ring-1 ring-foreground/10 [--card-spacing:--spacing(4)] has-data-[slot=card-footer]:pb-0 has-[>img:first-child]:pt-0 data-[size=sm]:[--card-spacing:--spacing(3)] data-[size=sm]:has-data-[slot=card-footer]:pb-0 *:[img:first-child]:rounded-t-xl *:[img:last-child]:rounded-b-xl",
        className
      )}
      {...props}
    />
  )
}

/**
 * Cabeçalho em grade. Com um `CardAction` dentro, ganha uma segunda
 * coluna à direita para a ação. É um contêiner `@container`, para o
 * conteúdo reagir à largura do card, e não à da tela.
 */
function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "group/card-header @container/card-header grid auto-rows-min items-start gap-1 rounded-t-xl px-(--card-spacing) has-data-[slot=card-action]:grid-cols-[1fr_auto] has-data-[slot=card-description]:grid-rows-[auto_auto] [.border-b]:pb-(--card-spacing)",
        className
      )}
      {...props}
    />
  )
}

/**
 * Título do card. É um `div`, não um heading: os padrões do admin põem um
 * `h2` dentro, para o título entrar no mapa de títulos da página.
 */
function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-title"
      className={cn(
        "font-heading text-base leading-snug font-medium group-data-[size=sm]/card:text-sm",
        className
      )}
      {...props}
    />
  )
}

/** Texto de apoio abaixo do título, em `--muted-foreground`. */
function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

/**
 * Ação no canto do cabeçalho, na segunda coluna da grade. Sem uso nas
 * telas: o `CardActionsMenu` da seção 14.6 ainda não existe.
 */
function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn(
        "col-start-2 row-span-2 row-start-1 self-start justify-self-end",
        className
      )}
      {...props}
    />
  )
}

/** Corpo do card, com o padding lateral de `--card-spacing`. */
function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-content"
      className={cn("px-(--card-spacing)", className)}
      {...props}
    />
  )
}

/** Rodapé com borda em cima e fundo `--muted` a 50%. Sem uso nas telas. */
function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn(
        "flex items-center rounded-b-xl border-t bg-muted/50 p-(--card-spacing)",
        className
      )}
      {...props}
    />
  )
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
}
