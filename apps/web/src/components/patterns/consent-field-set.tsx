/**
 * Aceites do cadastro: dois obrigatórios e dois opcionais, com o
 * consentimento sensível destacado (seções 14.6 e 15.5, passo de aceite).
 *
 * Aparece no fim do cadastro por conversa (`/register`) e no cadastro por
 * formulário (`/register/form`). É controlado: recebe os quatro aceites
 * em `value` e devolve o objeto inteiro em `onChange`. Os erros dos
 * obrigatórios vêm de `consentIssues`, no modelo do cadastro.
 *
 * Os opcionais começam desmarcados (`emptyConsents`). O de personalização
 * fica num bloco em `--warning`, porque tipo de visitante e motivo da
 * visita podem indicar que a pessoa é paciente (seção 11.4).
 *
 * Acessibilidade: um `fieldset` com legenda agrupa os aceites, e o
 * `disabled` dele trava todas as caixas durante o envio. Cada caixa tem
 * rótulo pelo `htmlFor` e liga a descrição e o erro no
 * `aria-describedby`. No celular, o rótulo e os links chegam a 44 px
 * (seção 15.8). O `data-highlighted` é o gancho do teste do cadastro.
 */
import { useId, type ReactNode } from "react"
import { Link } from "react-router"

import { Checkbox } from "@/components/ui/checkbox.tsx"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field.tsx"
import { Label } from "@/components/ui/label.tsx"
import { pt } from "@/i18n/pt.ts"
import { type Consents } from "@/features/registration/model.ts"

/** Os quatro aceites do cadastro, em grupos de obrigatórios e opcionais. */
export function ConsentFieldSet({
  value,
  onChange,
  errors,
  disabled,
}: {
  value: Consents
  onChange: (value: Consents) => void
  /** Mensagem por aceite obrigatório que falta. */
  errors: Partial<Record<"accept_terms" | "age_18_plus", string>>
  disabled: boolean
}) {
  // Cada caixa muda só a própria chave e devolve o objeto completo.
  function update(patch: Partial<Consents>) {
    onChange({ ...value, ...patch })
  }

  return (
    <FieldSet disabled={disabled} className="gap-5">
      <FieldLegend>{pt.registration.consentsTitle}</FieldLegend>
      <FieldGroup>
        <p className="text-label text-muted-foreground">
          {pt.registration.requiredLegend}
        </p>
        <ConsentCheck
          checked={value.accept_terms}
          disabled={disabled}
          label={pt.registration.terms}
          error={errors.accept_terms}
          onCheckedChange={(checked) => update({ accept_terms: checked })}
          // Links para ler os Termos e o Aviso de Privacidade antes do
          // aceite; com 44 px no celular e 24 px no desktop.
          description={
            <span className="flex flex-wrap gap-3">
              <Link
                to="/terms"
                className="inline-flex min-h-11 items-center underline underline-offset-4 md:min-h-6"
              >
                {pt.registration.termsLink}
              </Link>
              <Link
                to="/privacy"
                className="inline-flex min-h-11 items-center underline underline-offset-4 md:min-h-6"
              >
                {pt.registration.privacyLink}
              </Link>
            </span>
          }
        />
        <ConsentCheck
          checked={value.age_18_plus}
          disabled={disabled}
          label={pt.registration.age}
          error={errors.age_18_plus}
          onCheckedChange={(checked) => update({ age_18_plus: checked })}
        />
        <p className="text-label text-muted-foreground">
          {pt.registration.optionalLegend}
        </p>
        {/* O destaque é borda e fundo de `--warning` e um título em */}
        {/* texto, "Consentimento destacado": a cor não fala sozinha. */}
        <div
          data-highlighted="personalization"
          className="flex flex-col gap-2 rounded-2xl border border-warning bg-[color-mix(in_oklab,var(--warning)_15%,transparent)] p-4"
        >
          <p className="text-label text-foreground">
            {pt.registration.personalizationBadge}
          </p>
          <ConsentCheck
            checked={value.profile_personalization}
            disabled={disabled}
            label={pt.registration.personalization}
            onCheckedChange={(checked) =>
              update({ profile_personalization: checked })
            }
            description={pt.registration.personalizationNote}
          />
        </div>
        <ConsentCheck
          checked={value.quality_improvement}
          disabled={disabled}
          label={pt.registration.quality}
          onCheckedChange={(checked) =>
            update({ quality_improvement: checked })
          }
          description={pt.registration.qualityNote}
        />
      </FieldGroup>
    </FieldSet>
  )
}

/**
 * Uma caixa de aceite com rótulo, descrição e erro, na orientação
 * horizontal do `Field`.
 */
function ConsentCheck({
  checked,
  disabled,
  label,
  error,
  description,
  onCheckedChange,
}: {
  checked: boolean
  disabled: boolean
  label: string
  error?: string
  description?: ReactNode
  onCheckedChange: (checked: boolean) => void
}) {
  const id = useId()
  const errorId = useId()
  const descriptionId = useId()
  // Junta só os ids que existem; sem nenhum, o atributo nem é escrito.
  const describedBy = [
    description ? descriptionId : null,
    error ? errorId : null,
  ]
    .filter(Boolean)
    .join(" ")

  return (
    <Field
      orientation="horizontal"
      data-invalid={error ? true : undefined}
      data-disabled={disabled || undefined}
    >
      <Checkbox
        id={id}
        checked={checked}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        // O Radix pode mandar `"indeterminate"`; aqui só `true` marca.
        onCheckedChange={(next) => onCheckedChange(next === true)}
      />
      <FieldContent>
        <Label htmlFor={id} className="max-md:min-h-11">
          {label}
        </Label>
        {description ? (
          <FieldDescription id={descriptionId}>{description}</FieldDescription>
        ) : null}
        {error ? <FieldError id={errorId}>{error}</FieldError> : null}
      </FieldContent>
    </Field>
  )
}
