/**
 * Campo de texto de várias linhas do shadcn/ui: um `<textarea>` com
 * classes, sem primitivo do Radix.
 *
 * É o campo do `Composer` (início e conversa) e o das mensagens do
 * cadastro por conversa, do canal do titular em `/privacy`, da nota de
 * resolução em `/admin/privacy` e do motivo de revelar identidade em
 * `/admin/quality`.
 *
 * O que o projeto mudou no gerado pelo shadcn: 44 px de altura mínima no
 * celular e 32 px no desktop (seção 15.8), `text-body`, sem a alça de
 * redimensionar, borda `--danger` com `aria-invalid` e cursor padrão
 * quando desabilitado. `field-sizing-content` faz o campo crescer com o
 * texto nos navegadores que têm essa propriedade.
 *
 * Atenção: `outline-none` vence o contorno de foco global, porque a camada
 * `utilities` do Tailwind vem depois da `base`, e o campo não tem anel
 * próprio. Só o cadastro por conversa mostra o foco, pela borda do
 * contêiner (`focus-within:border-ring`). Nos outros usos, inclusive no
 * `Composer`, o foco fica sem o anel da seção 14.7.
 */
import * as React from "react"
import { cn } from "cn"

/**
 * Campo com todas as props de `<textarea>`. O `ref` passa como prop comum
 * (React 19): o `Composer` o usa para ajustar a altura ao conteúdo.
 */
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-11 w-full resize-none rounded-lg border border-input bg-transparent px-3 py-2 text-body text-foreground transition-colors outline-none placeholder:text-muted-foreground disabled:cursor-default disabled:opacity-50 aria-invalid:border-danger md:min-h-8",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
