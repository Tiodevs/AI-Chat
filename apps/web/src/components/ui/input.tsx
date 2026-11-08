/**
 * Campo de texto de uma linha do shadcn/ui: um `<input>` com classes, sem
 * primitivo do Radix.
 *
 * Aparece em entrar, cadastro por formulário, conta, canal do titular,
 * envio de documento, `PasswordCard`, `ProfileSummaryCard` e
 * `SearchDialog`.
 *
 * O que o projeto mudou no gerado pelo shadcn:
 * - `max-md:min-h-11`: 44 px abaixo de 768 px (seção 15.8).
 * - Sem `outline-none` e sem anel próprio: vale o contorno de foco global
 *   de 2 px (seção 14.7).
 * - Cursor padrão quando desabilitado (seção 14.7).
 * - Sem o anel de `aria-invalid`: o erro aparece na borda `--danger`, e a
 *   mensagem fica no `FieldError`.
 *
 * A borda `border-input` lê `--input`, que `tokens.css` liga a
 * `--border-strong`, o token de campos da seção 14.2. Seção 14.6.
 */
import * as React from "react"
import { cn } from "cn"

/**
 * Campo com todas as props de `<input>`. O `ref` passa como prop comum
 * (React 19), como no `PasswordCard`, que move o foco para o campo.
 */
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-8 max-md:min-h-11 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground disabled:pointer-events-none disabled:cursor-default disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive md:text-sm dark:bg-input/30 dark:disabled:bg-input/80",
        className
      )}
      {...props}
    />
  )
}

export { Input }
