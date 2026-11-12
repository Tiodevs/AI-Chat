/**
 * Compositor da pergunta: campo que cresce, Enviar, Parar e o aviso de
 * saúde (seção 14.6).
 *
 * Aparece na página inicial (`/`), em destaque, e fixo embaixo da
 * conversa (`/ask/:id?`) (seção 15.5). É controlado: o texto vive na tela,
 * e o envio sobe por `onSubmit` para o `useAskConversation`.
 *
 * Estados:
 * - Em repouso: Enviar desabilitado com o campo vazio.
 * - Enviando (`pending`): Enviar com spinner, "Enviando" e `aria-busy`.
 * - Em fluxo (`streaming`): o campo fica desabilitado, e Parar toma o
 *   lugar de Enviar. A Etapa 14.3 do plano troca o `disabled` por
 *   `readOnly` com `aria-disabled` e devolve o foco ao campo.
 * - Desabilitado (`disabled`, com o orçamento estourado): o motivo, com o
 *   telefone da mesa, aparece abaixo do campo.
 * - Inválido (`error`): `aria-invalid` e o `FieldError`.
 *
 * Acessibilidade: o rótulo é visível; a dica de saúde e o erro entram no
 * `aria-describedby`. Enter envia e Shift+Enter quebra a linha (seção
 * 15.8). Botões de 44 px no celular. O aviso de saúde protege o que a IA
 * não deve ver (seção 15.6).
 */
import { useEffect, useId, useRef } from "react"

import { Button } from "@/components/ui/button.tsx"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { Textarea } from "@/components/ui/textarea.tsx"
import { pt } from "@/i18n/pt.ts"

/** Formulário da pergunta. */
export function Composer({
  value,
  onChange,
  onSubmit,
  onStop,
  streaming,
  pending,
  disabled,
  disabledReason,
  error,
  label = pt.ask.questionLabel,
  placeholder = pt.ask.placeholder,
  hint = pt.ask.healthHint,
  maxLength = 1000,
}: {
  value: string
  onChange: (value: string) => void
  /** Pede o envio; o chamador lê o `value` e limpa o campo. */
  onSubmit: () => void
  /** Interrompe a resposta em fluxo (botão Parar). */
  onStop: () => void
  /** A resposta está chegando: mostra Parar no lugar de Enviar. */
  streaming: boolean
  /** O envio saiu e ainda não começou a responder. */
  pending: boolean
  /** Bloqueio que não passa sozinho, como o orçamento diário estourado. */
  disabled: boolean
  /** Texto do bloqueio, mostrado só com `disabled`. */
  disabledReason: string | null
  error: string | null
  /**
   * Rótulo, texto de exemplo, dica e limite do campo. No atendimento
   * humano, a conversa troca os da pergunta pelos da equipe e a dica de
   * saúde pelo aviso da seção 29.9.5.
   */
  label?: string
  placeholder?: string
  hint?: string
  maxLength?: number
}) {
  const fieldId = useId()
  const hintId = useId()
  const errorId = useId()
  const fieldRef = useRef<HTMLTextAreaElement>(null)
  const blocked = disabled || streaming

  // O campo cresce com o texto: zera a altura para `auto` e aplica a
  // altura do conteúdo (`scrollHeight`) a cada mudança. Não é animação: a
  // altura muda direto.
  useEffect(() => {
    const field = fieldRef.current
    if (!field) {
      return
    }
    field.style.height = "auto"
    field.style.height = `${field.scrollHeight}px`
  }, [value])

  // O Enter e o botão passam por aqui, e nada sai durante um bloqueio.
  function submit() {
    if (blocked || pending) {
      return
    }
    onSubmit()
  }

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <Field
        data-disabled={disabled ? true : undefined}
        data-invalid={error ? true : undefined}
      >
        <FieldLabel htmlFor={fieldId}>{label}</FieldLabel>
        <Textarea
          ref={fieldRef}
          id={fieldId}
          value={value}
          rows={2}
          // O limite de 1.000 caracteres da API (seções 12 e 29.8).
          maxLength={maxLength}
          placeholder={placeholder}
          // Desabilitar o campo focado durante o fluxo tira o foco dele;
          // é o achado da Etapa 14.3.
          disabled={blocked}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${hintId} ${errorId}` : hintId}
          onChange={(event) => {
            onChange(event.target.value)
          }}
          // Enter envia; Shift+Enter segue o padrão e quebra a linha.
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault()
              submit()
            }
          }}
        />
        {/* O aviso de saúde da seção 15.6, lido junto com o campo. */}
        <FieldDescription id={hintId}>{hint}</FieldDescription>
        {error ? <FieldError id={errorId}>{error}</FieldError> : null}
        {disabled && disabledReason ? (
          <p className="text-body text-foreground">{disabledReason}</p>
        ) : null}
      </Field>
      <div className="flex justify-end">
        {streaming ? (
          <Button
            type="button"
            className="min-h-11 md:min-h-8"
            onClick={onStop}
          >
            {pt.ask.stop}
          </Button>
        ) : (
          <Button
            type="submit"
            className="min-h-11 md:min-h-8"
            disabled={disabled || pending || value.trim() === ""}
            aria-busy={pending || undefined}
          >
            {/* Sem `aria-hidden`, o spinner soma "Carregando" ao nome do */}
            {/* botão; os outros botões de envio o escondem. */}
            {pending ? <Spinner /> : null}
            {pending ? pt.ask.sending : pt.ask.send}
          </Button>
        )}
      </div>
    </form>
  )
}
