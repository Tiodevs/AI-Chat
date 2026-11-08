/**
 * Passo da senha, fora do chat, com medidor de força (seções 14.6 e
 * 15.6, proteger o que a IA não deve ver).
 *
 * No cadastro por conversa (`/register`), toma o lugar do compositor e
 * envia sozinho, com `onSubmit` (seção 15.5). No cadastro por formulário
 * (`/register/form`), vira só um campo do formulário da página, sem
 * `onSubmit`. A nota "Sua senha vai direto para o nosso servidor. A IA
 * não a vê." aparece nos dois.
 *
 * Acessibilidade: o campo usa `autoComplete="new-password"`, para o
 * gerenciador de senhas sugerir uma senha nova. A dica e o medidor entram
 * no `aria-describedby`, e o medidor tem `role="meter"` com o nível em
 * texto (`aria-valuetext`), não só na barra.
 *
 * Movimento: M12 (seção 16.3), o preset `enterPassword`, com `autoAlpha`
 * e `y` de 12 a 0 em `duration.slow`. Com `moveFocus`, o foco vai ao
 * campo no `onComplete`; com movimento reduzido, o preset chama o
 * `onComplete` na hora (seção 16.6).
 */
import { useId, useRef } from "react"

import { Button } from "@/components/ui/button.tsx"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field.tsx"
import { Input } from "@/components/ui/input.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"
import { passwordStrength } from "@/features/registration/model.ts"

/** Cartão da senha, com campo, medidor, nota e, no chat, Enviar. */
export function PasswordCard({
  value,
  onChange,
  onSubmit,
  pending,
  error,
  moveFocus,
}: {
  value: string
  onChange: (value: string) => void
  /** Com ele, o cartão é um formulário com Enviar; sem ele, só o campo. */
  onSubmit?: () => void
  pending: boolean
  error: string | null
  /** Põe o foco no campo ao fim da entrada; o chat liga, a página não. */
  moveFocus: boolean
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const fieldId = useId()
  const errorId = useId()
  const meterId = useId()
  const { reduced } = useMotion()
  // Nível de 0 a 4 pelo tamanho (12 a 72) e pelos tipos de caractere;
  // a regra fica em `passwordStrength`, no modelo do cadastro.
  const strength = passwordStrength(value)
  const strengthText = pt.registration.strength[strength.level]

  // M12. O foco espera o fim da entrada: um campo ainda invisível não
  // deve receber o foco.
  useGSAP(
    () => {
      presets.enterPassword(rootRef.current, reduced, () => {
        if (moveFocus) {
          inputRef.current?.focus()
        }
      })
    },
    { scope: rootRef, dependencies: [reduced, moveFocus] }
  )

  const body = (
    <>
      <Field
        data-invalid={error ? true : undefined}
        data-disabled={pending || undefined}
      >
        <FieldLabel htmlFor={fieldId}>
          {pt.registration.fields.password}
        </FieldLabel>
        <Input
          ref={inputRef}
          id={fieldId}
          type="password"
          autoComplete="new-password"
          value={value}
          disabled={pending}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${meterId} ${errorId}` : meterId}
          className="h-11 md:h-8"
          onChange={(event) => onChange(event.target.value)}
        />
        <FieldDescription id={meterId}>
          {pt.registration.passwordHint}
        </FieldDescription>
        <StrengthMeter score={strength.score} text={strengthText} />
        {error ? <FieldError id={errorId}>{error}</FieldError> : null}
      </Field>
      <p className="text-body text-foreground">
        {pt.registration.passwordNote}
      </p>
      {onSubmit ? (
        <Button
          type="submit"
          className="min-h-11 md:min-h-8"
          disabled={pending || value === ""}
        >
          {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
          {pending ? pt.registration.sending : pt.registration.send}
        </Button>
      ) : null}
    </>
  )

  // No chat, o cartão tem o próprio `<form>`. Na página, ele já está
  // dentro do formulário do cadastro, e um `<form>` aninhado é inválido.
  const fields = onSubmit ? (
    <form
      aria-label={pt.registration.passwordForm}
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      {body}
    </form>
  ) : (
    <div className="flex flex-col gap-4">{body}</div>
  )

  return (
    <div ref={rootRef} className="rounded-card bg-card p-4 md:p-5">
      {fields}
    </div>
  )
}

/**
 * Medidor de força: `role="meter"` de 0 a 4, com o nível em texto. A
 * barra é `aria-hidden` e cresce com `scaleX`, sem mudar a largura
 * (seção 16.1); ela muda direto, sem animação.
 */
function StrengthMeter({ score, text }: { score: number; text: string }) {
  return (
    <div className="flex flex-col gap-2">
      <div
        role="meter"
        aria-label={pt.registration.strengthLabel}
        aria-valuemin={0}
        aria-valuemax={4}
        aria-valuenow={score}
        aria-valuetext={text}
        className="h-1 overflow-hidden rounded-full bg-muted"
      >
        <div
          aria-hidden="true"
          className="h-full w-full origin-left bg-foreground"
          style={{ transform: `scaleX(${score / 4})` }}
        />
      </div>
      <p className="text-caption text-foreground">{text}</p>
    </div>
  )
}
