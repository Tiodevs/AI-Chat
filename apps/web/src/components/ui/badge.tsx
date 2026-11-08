/**
 * Selo curto de status, do shadcn/ui (`radix-nova`). É um `<span>` com
 * classes; o Radix só entra pelo `Slot`, no `asChild`.
 *
 * Aparece no status dos documentos (`/admin/documents`), no desfecho e na
 * avaliação das conversas (`/admin/quality`), no status dos pedidos de
 * titular (`/admin/privacy`) e dentro do `DueDateBadge`.
 *
 * O projeto acrescentou as variantes `info`, `success`, `warning` e
 * `danger`: o par de status da seção 14.2, com o fundo da cor a 15% e o
 * texto em `--foreground`, que mantém o contraste. A cor só reforça; o
 * texto do selo diz o estado (seção 15.8). Seção 14.6 do SDD.
 */
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

/**
 * Classes do selo por `cva`. `rounded-4xl` com 20 px de altura forma a
 * pílula da seção 14.4. `[&>svg]:size-3!` força ícones de 12 px, abaixo
 * dos 14 px que a seção 14.4 pede para badges.
 *
 * - `default`, `secondary`, `destructive`, `outline`, `ghost` e `link`:
 *   as do shadcn. O projeto usa `secondary` como o selo neutro: documento
 *   arquivado, prazo em dia ou fechado, desfecho sem tom.
 * - `info`, `success`, `warning` e `danger`: os tons de status, com o
 *   fundo por `color-mix` do token com transparente.
 */
const badgeVariants = cva(
  "group/badge inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-4xl border border-transparent px-2 py-0.5 text-xs font-medium whitespace-nowrap transition-all focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground [a]:hover:bg-primary/80",
        secondary:
          "bg-secondary text-secondary-foreground [a]:hover:bg-secondary/80",
        destructive:
          "bg-destructive/10 text-destructive focus-visible:ring-destructive/20 dark:bg-destructive/20 dark:focus-visible:ring-destructive/40 [a]:hover:bg-destructive/20",
        outline:
          "border-border text-foreground [a]:hover:bg-muted [a]:hover:text-muted-foreground",
        ghost:
          "hover:bg-muted hover:text-muted-foreground dark:hover:bg-muted/50",
        link: "text-primary underline-offset-4 hover:underline",
        info: "bg-[color-mix(in_oklab,var(--info)_15%,transparent)] text-foreground",
        success:
          "bg-[color-mix(in_oklab,var(--success)_15%,transparent)] text-foreground",
        warning:
          "bg-[color-mix(in_oklab,var(--warning)_15%,transparent)] text-foreground",
        danger:
          "bg-[color-mix(in_oklab,var(--danger)_15%,transparent)] text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

/**
 * Selo com as variantes de `badgeVariants`. Com `asChild`, o estilo vai
 * para o filho, como um link. `data-variant` deixa os testes conferirem o
 * tom, como faz `features/admin/privacy-queue.test.tsx`.
 */
function Badge({
  className,
  variant = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
