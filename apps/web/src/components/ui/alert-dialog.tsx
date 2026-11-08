/**
 * Diálogo de confirmação sobre o `AlertDialog` do Radix, do shadcn/ui
 * (`radix-nova`).
 *
 * Usado onde uma ação não tem volta: Excluir minha conta, na aba
 * Privacidade de `/account`, e Arquivar, em `/admin/documents` (seção
 * 15.5). Diferente do `Dialog`, o Radix dá o papel `alertdialog`, não
 * fecha com um clique fora e põe o foco em Cancelar ao abrir.
 *
 * O que o projeto mudou no gerado pelo shadcn:
 * - Fundo `bg-overlay`, conteúdo em `--popover` com `shadow-overlay` e a
 *   borda `--border` (seção 14.4).
 * - Sem as animações de CSS: o diálogo aparece e some direto. A M14 da
 *   seção 16.3 prevê `useGsapPresence` em diálogos, e este não o usa.
 * - `AlertDialogAction` usa a variante `destructive` por padrão, porque
 *   as duas telas confirmam exclusão ou arquivamento.
 * - Ação e Cancelar com 44 px no celular e 32 px no desktop (seção 15.8).
 */
import * as React from "react"
import { cn } from "cn"
import { AlertDialog as AlertDialogPrimitive } from "radix-ui"

import { Button } from "@/components/ui/button"

/** Raiz do diálogo de confirmação. Controla `open` e `onOpenChange`. */
function AlertDialog({
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Root>) {
  return <AlertDialogPrimitive.Root data-slot="alert-dialog" {...props} />
}

/** Botão que abre a confirmação, quase sempre com `asChild`. */
function AlertDialogTrigger({
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Trigger>) {
  return (
    <AlertDialogPrimitive.Trigger data-slot="alert-dialog-trigger" {...props} />
  )
}

/** Leva o fundo e o conteúdo para o fim do `body`. */
function AlertDialogPortal({
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Portal>) {
  return (
    <AlertDialogPrimitive.Portal data-slot="alert-dialog-portal" {...props} />
  )
}

/** Fundo escuro atrás do diálogo. Clicar nele não fecha a confirmação. */
function AlertDialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Overlay>) {
  return (
    <AlertDialogPrimitive.Overlay
      data-slot="alert-dialog-overlay"
      className={cn("fixed inset-0 isolate z-50 bg-overlay", className)}
      {...props}
    />
  )
}

/** Caixa centrada da confirmação, já com o portal e o fundo. */
function AlertDialogContent({
  className,
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Content>) {
  return (
    <AlertDialogPortal>
      <AlertDialogOverlay />
      <AlertDialogPrimitive.Content
        data-slot="alert-dialog-content"
        className={cn(
          "fixed top-1/2 left-1/2 z-50 grid w-full max-w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl bg-popover p-4 text-sm text-popover-foreground shadow-overlay ring-1 ring-border sm:max-w-md",
          className
        )}
        {...props}
      />
    </AlertDialogPortal>
  )
}

/** Coluna de título e descrição. */
function AlertDialogHeader({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-dialog-header"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  )
}

/**
 * Faixa dos botões. No celular, empilha em ordem invertida
 * (`flex-col-reverse`), e a ação, que vem depois de Cancelar, fica em
 * cima; a partir de `sm`, alinha à direita.
 */
function AlertDialogFooter({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-dialog-footer"
      className={cn(
        "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
        className
      )}
      {...props}
    />
  )
}

/** Título, o nome que o leitor de tela anuncia ao abrir (seção 14.8). */
function AlertDialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Title>) {
  return (
    <AlertDialogPrimitive.Title
      data-slot="alert-dialog-title"
      className={cn(
        "font-heading text-base leading-none font-medium",
        className
      )}
      {...props}
    />
  )
}

/** O que a ação faz e que não tem volta. Ligado por `aria-describedby`. */
function AlertDialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Description>) {
  return (
    <AlertDialogPrimitive.Description
      data-slot="alert-dialog-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

/**
 * Botão que confirma e fecha. O `Button` com `asChild` empresta o estilo
 * ao `Action` do Radix, que continua sendo o elemento clicável. A
 * variante padrão é `destructive`.
 */
function AlertDialogAction({
  className,
  variant = "destructive",
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Action> &
  Pick<React.ComponentProps<typeof Button>, "variant">) {
  return (
    <Button variant={variant} asChild>
      <AlertDialogPrimitive.Action
        data-slot="alert-dialog-action"
        className={cn("min-h-11 md:min-h-8", className)}
        {...props}
      />
    </Button>
  )
}

/** Botão que fecha sem agir, em `outline`. Recebe o foco ao abrir. */
function AlertDialogCancel({
  className,
  variant = "outline",
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Cancel> &
  Pick<React.ComponentProps<typeof Button>, "variant">) {
  return (
    <Button variant={variant} asChild>
      <AlertDialogPrimitive.Cancel
        data-slot="alert-dialog-cancel"
        className={cn("min-h-11 md:min-h-8", className)}
        {...props}
      />
    </Button>
  )
}

export {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogTitle,
  AlertDialogTrigger,
}
