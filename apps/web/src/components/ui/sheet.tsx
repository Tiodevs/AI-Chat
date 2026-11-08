/**
 * Painel lateral do shadcn/ui (`radix-nova`), feito com o `Dialog` do
 * Radix: um diálogo modal preso a uma borda da tela (`side`), com o mesmo
 * foco preso, Esc e volta do foco.
 *
 * Usado na barra lateral do celular (`MobileSidebar`) e nos painéis do
 * admin: substituir documento (`/admin/documents`), inspetor de conversa
 * (`/admin/quality`) e pedido de titular (`/admin/privacy`).
 *
 * O que o projeto mudou no gerado pelo shadcn:
 * - Fundo `bg-overlay` e sombra `shadow-overlay` (seção 14.4).
 * - Sem as animações de CSS de deslizar e esmaecer. Só o `MobileSidebar`
 *   anima, com `forceMount` e `useGsapPresence` (M14); os sheets do admin
 *   abrem e fecham direto.
 * - Botão de fechar com 44 px (`size-11`), ícone de traço 1,75 e o nome
 *   "Fechar" de `pt.close`, em `sr-only`.
 *
 * Todo sheet tem `SheetTitle`, mesmo escondido (seção 14.8). O
 * `"use client"` veio do modelo do shadcn e não tem efeito numa SPA do
 * Vite.
 */
"use client"

import * as React from "react"
import { cn } from "cn"
import { Dialog as SheetPrimitive } from "radix-ui"

import { Button } from "@/components/ui/button"
import { pt } from "@/i18n/pt"
import { XIcon } from "lucide-react"

/** Raiz do painel. Controla `open` e `onOpenChange`. */
function Sheet({ ...props }: React.ComponentProps<typeof SheetPrimitive.Root>) {
  return <SheetPrimitive.Root data-slot="sheet" {...props} />
}

/** Botão que abre o painel. Sem uso: as telas abrem por estado. */
function SheetTrigger({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Trigger>) {
  return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />
}

/** Qualquer elemento que fecha o painel ao ser clicado. Sem uso nas telas. */
function SheetClose({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Close>) {
  return <SheetPrimitive.Close data-slot="sheet-close" {...props} />
}

/** Leva o fundo e o painel para o fim do `body`. */
function SheetPortal({
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Portal>) {
  return <SheetPrimitive.Portal data-slot="sheet-portal" {...props} />
}

/** Fundo escuro atrás do painel. Um clique nele fecha o painel. */
function SheetOverlay({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Overlay>) {
  return (
    <SheetPrimitive.Overlay
      data-slot="sheet-overlay"
      className={cn(
        "fixed inset-0 z-50 bg-overlay",
        className
      )}
      {...props}
    />
  )
}

/**
 * O painel, já com o portal e o fundo. `side` vai para `data-side`, que
 * escolhe a borda e o tamanho: nas laterais, 3/4 da tela, até 384 px a
 * partir de `sm`. Com `showCloseButton` (padrão), desenha o X no canto.
 */
function SheetContent({
  className,
  children,
  side = "right",
  showCloseButton = true,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & {
  side?: "top" | "right" | "bottom" | "left"
  showCloseButton?: boolean
}) {
  return (
    <SheetPortal>
      <SheetOverlay />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        data-side={side}
        className={cn(
          "fixed z-50 flex flex-col gap-4 bg-popover bg-clip-padding text-sm text-popover-foreground shadow-overlay data-[side=bottom]:inset-x-0 data-[side=bottom]:bottom-0 data-[side=bottom]:h-auto data-[side=bottom]:border-t data-[side=left]:inset-y-0 data-[side=left]:left-0 data-[side=left]:h-full data-[side=left]:w-3/4 data-[side=left]:border-r data-[side=right]:inset-y-0 data-[side=right]:right-0 data-[side=right]:h-full data-[side=right]:w-3/4 data-[side=right]:border-l data-[side=top]:inset-x-0 data-[side=top]:top-0 data-[side=top]:h-auto data-[side=top]:border-b data-[side=left]:sm:max-w-sm data-[side=right]:sm:max-w-sm",
          className
        )}
        {...props}
      >
        {children}
        {showCloseButton && (
          <SheetPrimitive.Close data-slot="sheet-close" asChild>
            <Button
              variant="ghost"
              className="absolute top-3 right-3 size-11"
              size="icon"
            >
              <XIcon strokeWidth={1.75} />
              <span className="sr-only">{pt.close}</span>
            </Button>
          </SheetPrimitive.Close>
        )}
      </SheetPrimitive.Content>
    </SheetPortal>
  )
}

/** Topo do painel, com título e descrição. */
function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-header"
      className={cn("flex flex-col gap-0.5 p-4", className)}
      {...props}
    />
  )
}

/** Pé do painel, empurrado para baixo com `mt-auto`. */
function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-footer"
      className={cn("mt-auto flex flex-col gap-2 p-4", className)}
      {...props}
    />
  )
}

/**
 * Título do painel, ligado por `aria-labelledby`. O `MobileSidebar` o
 * esconde com `sr-only`, sem tirá-lo do leitor de tela (seção 14.8).
 */
function SheetTitle({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Title>) {
  return (
    <SheetPrimitive.Title
      data-slot="sheet-title"
      className={cn(
        "font-heading text-base font-medium text-foreground",
        className
      )}
      {...props}
    />
  )
}

/** Descrição curta, ligada por `aria-describedby`. */
function SheetDescription({
  className,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Description>) {
  return (
    <SheetPrimitive.Description
      data-slot="sheet-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Sheet,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
}
