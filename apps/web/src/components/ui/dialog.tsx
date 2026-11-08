/**
 * Diálogo modal sobre o `Dialog` do Radix, do shadcn/ui (`radix-nova`).
 *
 * Usado pelo `SearchDialog`, a busca do `⌘K`. O Radix dá o papel `dialog`
 * com `aria-modal`, prende o foco dentro, fecha com Esc ou com um clique
 * fora e devolve o foco a quem abriu.
 *
 * O que o projeto mudou no gerado pelo shadcn:
 * - Fundo `bg-overlay` (`--overlay`). Conteúdo em `--popover`, com a
 *   sombra `shadow-overlay` e a borda `--border` da seção 14.4.
 * - Sem as animações de CSS (`animate-in`, `zoom-in`): o movimento de
 *   abrir e fechar é do GSAP (M14). O `SearchDialog` passa `forceMount`
 *   e anima o conteúdo com `useGsapPresence`.
 * - Botão de fechar com 44 px (`size-11`, seção 15.8), ícone de traço
 *   1,75 (seção 14.4) e o nome "Fechar" de `pt.close`, em `sr-only`.
 *
 * Todo diálogo tem `DialogTitle`, mesmo escondido (seção 14.8).
 */
import * as React from "react"
import { cn } from "cn"
import { Dialog as DialogPrimitive } from "radix-ui"

import { Button } from "@/components/ui/button"
import { pt } from "@/i18n/pt"
import { XIcon } from "lucide-react"

/** Raiz do diálogo. Controla `open` e `onOpenChange`. */
function Dialog({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

/** Botão que abre o diálogo. Sem uso nas telas: a busca abre por estado. */
function DialogTrigger({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

/** Leva o fundo e o conteúdo para o fim do `body`, fora do layout. */
function DialogPortal({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Portal>) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

/** Qualquer elemento que fecha o diálogo ao ser clicado. */
function DialogClose({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

/** Fundo escuro que cobre a página atrás do diálogo. */
function DialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        "fixed inset-0 isolate z-50 bg-overlay",
        className
      )}
      {...props}
    />
  )
}

/**
 * Caixa do diálogo, centrada, já com o portal e o fundo. Com
 * `showCloseButton` (padrão), desenha o X no canto. `forceMount` mantém o
 * conteúdo montado para o GSAP animar; o `SearchDialog` decide quando
 * montar.
 */
function DialogContent({
  className,
  children,
  showCloseButton = true,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
  showCloseButton?: boolean
}) {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          "fixed top-1/2 left-1/2 z-50 grid w-full max-w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl bg-popover p-4 text-sm text-popover-foreground shadow-overlay ring-1 ring-border sm:max-w-md",
          className
        )}
        {...props}
      >
        {children}
        {/* 44 px também no desktop; o nome vem do texto em `sr-only`. */}
        {showCloseButton && (
          <DialogPrimitive.Close data-slot="dialog-close" asChild>
            <Button
              variant="ghost"
              className="absolute top-2 right-2 size-11"
              size="icon"
            >
              <XIcon strokeWidth={1.75} />
              <span className="sr-only">{pt.close}</span>
            </Button>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPortal>
  )
}

/** Coluna de título e descrição no topo do diálogo. */
function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  )
}

/**
 * Faixa de ações no pé do diálogo. No celular, os botões empilham em
 * ordem invertida (`flex-col-reverse`): o último, em geral a ação
 * principal, fica em cima. Com `showCloseButton`, acrescenta o botão
 * "Fechar". Sem uso nas telas.
 */
function DialogFooter({
  className,
  showCloseButton = false,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  showCloseButton?: boolean
}) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "-mx-4 -mb-4 flex flex-col-reverse gap-2 rounded-b-xl border-t bg-muted/50 p-4 sm:flex-row sm:justify-end",
        className
      )}
      {...props}
    >
      {children}
      {showCloseButton && (
        <DialogPrimitive.Close asChild>
          <Button variant="outline">{pt.close}</Button>
        </DialogPrimitive.Close>
      )}
    </div>
  )
}

/**
 * Título do diálogo. O Radix liga o diálogo a ele por `aria-labelledby`,
 * e é esse o nome que o leitor de tela anuncia ao abrir (seção 14.8).
 */
function DialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn(
        "font-heading text-base leading-none font-medium",
        className
      )}
      {...props}
    />
  )
}

/** Descrição curta, ligada ao diálogo por `aria-describedby`. */
function DialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn(
        "text-sm text-muted-foreground *:[a]:underline *:[a]:underline-offset-3 *:[a]:hover:text-foreground",
        className
      )}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
}
