/**
 * Botão de toda a interface, do shadcn/ui (estilo `radix-nova`). É um
 * `<button>` com classes; o Radix só entra pelo `Slot`, no `asChild`.
 *
 * Aparece em todas as telas: Enviar e Parar no `Composer`, as ações do
 * admin, os diálogos, os sheets e o `RequestIdCopy`. Com `asChild`, ele
 * empresta o estilo a um link, como nas ações do `GuestHeader`.
 *
 * O que o projeto mudou no gerado pelo shadcn:
 * - `max-md:min-h-11` na base e `max-md:min-w-11` nos tamanhos de ícone:
 *   alvo de 44 px abaixo de 768 px, o celular da seção 14.5 (seção 15.8).
 *   No desktop valem as alturas de 24 a 36 px, que cumprem o mínimo.
 * - Sem `outline-none`, sem anel de foco próprio e sem `transition-all`:
 *   vale o contorno de 2 px em `--ring` de `globals.css` (seção 14.7).
 * - Sem o deslocamento de `active:` do shadcn. O aperto M16 da seção 16.3
 *   tem o preset `press`, mas nenhum componente o chama ainda.
 *
 * As cores vêm só de tokens semânticos (seção 14.2): `bg-primary` lê
 * `--primary`. Seção 14.6 do SDD.
 */
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

/**
 * Classes do botão por `cva` (class-variance-authority): a base vale
 * sempre, e cada chave de `variants` soma as classes da opção escolhida.
 *
 * `variant`:
 * - `default`: a ação principal, em `--primary` (branco sobre preto).
 * - `outline`: borda e fundo da tela; ações secundárias.
 * - `secondary`: fundo `--secondary`, que é o `--muted`.
 * - `ghost`: sem fundo até o hover; ícones e itens de navegação.
 * - `destructive`: texto `--danger` sobre o próprio `--danger` a 10%.
 * - `link`: texto sublinhado no hover, sem caixa.
 *
 * `size`: `xs` (24 px), `sm` (28), `default` (32) e `lg` (36) de altura,
 * e os quadrados `icon-xs` a `icon-lg` para botões só de ícone.
 *
 * `has-data-[icon=inline-start]` encurta o padding do lado de um ícone
 * marcado com `data-icon`, como o `Spinner` dos botões de envio.
 */
const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center max-md:min-h-11 rounded-lg border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap select-none disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/80",
        outline:
          "border-border bg-background hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:border-input dark:bg-input/30 dark:hover:bg-input/50",
        // No hover, mistura 5% de `--foreground` no fundo: a superfície
        // sobe um degrau de luminosidade (seção 14.7).
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-[color-mix(in_oklch,var(--secondary),var(--foreground)_5%)] aria-expanded:bg-secondary aria-expanded:text-secondary-foreground",
        ghost:
          "hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:hover:bg-muted/50",
        destructive:
          "bg-destructive/10 text-destructive hover:bg-destructive/20",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 rounded-[min(var(--radius-md),10px)] px-2 text-xs in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-[min(var(--radius-md),12px)] px-2.5 text-[0.8rem] in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        // Os quadrados ganham largura mínima de 44 px no celular, junto com
        // a altura mínima da base, para o alvo de toque da seção 15.8.
        icon: "size-8 max-md:min-w-11",
        "icon-xs":
          "size-6 max-md:min-w-11 rounded-[min(var(--radius-md),10px)] in-data-[slot=button-group]:rounded-lg [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 max-md:min-w-11 rounded-[min(var(--radius-md),12px)] in-data-[slot=button-group]:rounded-lg",
        "icon-lg": "size-9 max-md:min-w-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

/**
 * Botão com as variantes de `buttonVariants`.
 *
 * Com `asChild`, o `Slot` do Radix não cria um `<button>`: ele funde as
 * props e a classe no único filho, como um `<Link>` do React Router. Sem
 * `forwardRef`: no React 19, `ref` é uma prop comum, já incluída em
 * `React.ComponentProps<"button">`, e segue no `...props` até o elemento.
 * `data-variant` e `data-size` expõem a escolha para estilos e testes.
 */
function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  // O `cva` põe a `className` do chamador por último, e o `cn` resolve os
  // conflitos do Tailwind a favor dela: o `h-11 px-0` dos links da página
  // inicial substitui o `h-8 px-2.5` do tamanho `default`.
  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
