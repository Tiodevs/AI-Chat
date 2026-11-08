/**
 * Resumo do que a IA entendeu no cadastro por conversa, com cada campo
 * editável e o motivo de cada pergunta (seções 14.6 e 15.6, mostrar o que
 * a IA entendeu).
 *
 * Aparece em `/register`, aberto pelo botão "Ver o que entendemos": à
 * direita do chat no desktop e acima dele no celular (seção 15.5). Os
 * campos chegam da sessão de cadastro; a edição sobe por `onEdit`, que
 * grava na API e devolve se deu certo.
 *
 * Estados por campo: vazio ("Ainda não informado"), entendido (com o
 * visto), em edição, com erro (texto em `--danger` e ícone, com
 * `role="alert"`) e e-mail já cadastrado, que oferece Entrar.
 *
 * Acessibilidade: a seção tem o título como nome (`aria-labelledby`), e
 * uma região `aria-live="polite"` anuncia cada campo novo que a IA
 * entende. O link "Por que pedimos" é um disclosure com `aria-expanded`,
 * e os botões Editar levam o nome do campo em `sr-only`.
 *
 * Movimento: M10 (seção 16.3), o preset `confirmField`. Quando um campo
 * ganha valor, a camada `data-highlight` acende e apaga, e o visto
 * `data-confirm` cresce de 0,6 a 1 com `ease.confirm`. Com movimento
 * reduzido, só o visto aparece, sem destaque.
 */
import { useEffect, useId, useRef, useState } from "react"
import { CheckIcon, CircleAlert } from "lucide-react"
import { Link } from "react-router"

import { Button } from "@/components/ui/button.tsx"
import { Field, FieldLabel } from "@/components/ui/field.tsx"
import { Input } from "@/components/ui/input.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"
import {
  changedFieldAnnouncement,
  displayFieldValue,
  emailOffersSignIn,
  fieldLabel,
  fieldNames,
  visitReasons,
  visitorTypes,
  type FieldName,
  type RegistrationFields,
} from "@/features/registration/model.ts"

/** Cartão com os cinco campos do cadastro. */
export function ProfileSummaryCard({
  fields,
  fieldErrors,
  pending,
  onEdit,
  signInHref = "/sign-in",
}: {
  fields: RegistrationFields
  /** Erros do servidor por campo, como `email`. */
  fieldErrors: Record<string, string>
  /** Um envio está em curso: desabilita editar e salvar. */
  pending: boolean
  /** Grava um campo (`null` apaga) e devolve `true` se a API aceitou. */
  onEdit: (field: FieldName, value: string | null) => Promise<boolean>
  /** Destino do link Entrar, quando o e-mail já tem conta. */
  signInHref?: string
}) {
  const titleId = useId()
  const previous = useRef(fields)
  const [announcement, setAnnouncement] = useState("")

  // Compara com os campos da renderização anterior e anuncia só o que
  // mudou, no formato "Nome completo: Ana Costa". Um texto vazio não
  // substitui o anúncio anterior.
  useEffect(() => {
    const text = changedFieldAnnouncement(previous.current, fields)
    previous.current = fields
    if (text) {
      setAnnouncement(text)
    }
  }, [fields])

  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-4 rounded-card bg-card p-4 md:p-5"
    >
      <h2 id={titleId} className="text-label text-foreground">
        {pt.registration.summaryTitle}
      </h2>
      <div className="sr-only" role="status" aria-live="polite">
        {announcement}
      </div>
      <ul className="m-0 flex list-none flex-col gap-4 p-0">
        {fieldNames.map((name) => (
          <SummaryField
            key={name}
            name={name}
            value={fields[name]}
            error={fieldErrors[name] ?? null}
            pending={pending}
            signInHref={signInHref}
            onEdit={onEdit}
          />
        ))}
      </ul>
    </section>
  )
}

/**
 * Um campo do resumo: rótulo, valor ou editor, o motivo da pergunta, o
 * erro e, no e-mail já cadastrado, o link Entrar.
 */
function SummaryField({
  name,
  value,
  error,
  pending,
  signInHref,
  onEdit,
}: {
  name: FieldName
  value: string | null
  error: string | null
  pending: boolean
  signInHref: string
  onEdit: (field: FieldName, value: string | null) => Promise<boolean>
}) {
  const rootRef = useRef<HTMLLIElement>(null)
  const reasonId = useId()
  const { reduced } = useMotion()
  const [openReason, setOpenReason] = useState(false)
  const [editing, setEditing] = useState(false)
  const label = fieldLabel(name)
  // Tipo de visitante e motivo da visita viram o texto em português.
  const shown = displayFieldValue(name, value)
  const offerSignIn = name === "email" && emailOffersSignIn(error ?? undefined)

  // M10 a cada valor novo. Como o `useGSAP` também roda ao montar, os
  // campos já preenchidos piscam quando o cartão abre.
  useGSAP(
    () => {
      if (!value) {
        return
      }
      presets.confirmField(rootRef.current, reduced)
    },
    { scope: rootRef, dependencies: [value, reduced] }
  )

  return (
    <li ref={rootRef} className="relative flex flex-col gap-2">
      {/* Camada de destaque da M10: `--success` a 15%, começa invisível. */}
      <div
        data-highlight
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-lg bg-[color-mix(in_oklab,var(--success)_15%,transparent)] opacity-0"
      />
      <div className="relative flex flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <p className="text-label text-muted-foreground">{label}</p>
          {shown ? (
            <CheckIcon
              data-confirm
              aria-hidden="true"
              className="size-4 text-success"
            />
          ) : null}
        </div>
        {editing ? (
          <FieldEditor
            name={name}
            label={label}
            value={value}
            pending={pending}
            onCancel={() => setEditing(false)}
            onSave={async (next) => {
              const saved = await onEdit(name, next)
              if (saved) {
                setEditing(false)
              }
            }}
          />
        ) : (
          <div className="flex items-start justify-between gap-3">
            <p className="text-body text-foreground">
              {shown ?? pt.registration.summaryEmpty}
            </p>
            {/* O nome acessível é "Editar Nome completo": começa pelo */}
            {/* texto visível (WCAG 2.5.3) e diz qual campo muda. */}
            <Button
              type="button"
              variant="ghost"
              className="min-h-11 shrink-0 md:min-h-8"
              disabled={pending}
              onClick={() => setEditing(true)}
            >
              {pt.registration.edit}
              <span className="sr-only"> {label}</span>
            </Button>
          </div>
        )}
        {/* Disclosure: o link abre e fecha o motivo logo abaixo, sem */}
        {/* navegar. O motivo aparece quando o dado é pedido (15.1). */}
        <a
          href={`#${reasonId}`}
          className="w-fit text-body text-foreground underline underline-offset-4"
          aria-expanded={openReason}
          onClick={(event) => {
            event.preventDefault()
            setOpenReason((current) => !current)
          }}
        >
          {pt.registration.why}
          <span className="sr-only"> {label}</span>
        </a>
        <p
          id={reasonId}
          hidden={openReason ? undefined : true}
          className="text-body text-foreground"
        >
          {pt.registration.reasons[name]}
        </p>
        {error ? (
          <div
            role="alert"
            className="flex items-start gap-2 text-body text-danger"
          >
            <CircleAlert
              className="mt-0.5 size-4 shrink-0"
              aria-hidden="true"
            />
            <p>{error}</p>
          </div>
        ) : null}
        {offerSignIn ? (
          <Link
            to={signInHref}
            className="w-fit text-body text-foreground underline underline-offset-4"
          >
            {pt.registration.signIn}
          </Link>
        ) : null}
      </div>
    </li>
  )
}

/**
 * Editor de um campo, num formulário com o nome do campo. Tipo de
 * visitante e motivo da visita usam chips; os outros, um `Input` com o
 * `autoComplete` certo. Salvar manda o texto sem espaços nas pontas, ou
 * `null` quando fica vazio. O editor só fecha se a API aceitar.
 */
function FieldEditor({
  name,
  label,
  value,
  pending,
  onSave,
  onCancel,
}: {
  name: FieldName
  label: string
  value: string | null
  pending: boolean
  onSave: (value: string | null) => Promise<void>
  onCancel: () => void
}) {
  const inputId = useId()
  const [draft, setDraft] = useState(value ?? "")

  return (
    <form
      aria-label={label}
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        void onSave(draft.trim() ? draft.trim() : null)
      }}
    >
      {name === "visitor_type" || name === "visit_reason" ? (
        <ChoiceEditor
          name={name}
          label={label}
          value={draft}
          onChange={setDraft}
        />
      ) : (
        <Field data-disabled={pending || undefined}>
          <FieldLabel htmlFor={inputId}>{label}</FieldLabel>
          <Input
            id={inputId}
            value={draft}
            disabled={pending}
            autoComplete={autoCompleteFor(name)}
            type={
              name === "email" ? "email" : name === "phone" ? "tel" : "text"
            }
            className="h-11 md:h-8"
            onChange={(event) => setDraft(event.target.value)}
          />
        </Field>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          className="min-h-11 md:min-h-8"
          disabled={pending}
        >
          {pt.registration.save}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-11 md:min-h-8"
          disabled={pending}
          onClick={onCancel}
        >
          {pt.registration.cancel}
        </Button>
      </div>
    </form>
  )
}

/** Escolhe as opções e os textos do campo de escolha. */
function ChoiceEditor({
  name,
  label,
  value,
  onChange,
}: {
  name: "visitor_type" | "visit_reason"
  label: string
  value: string
  onChange: (value: string) => void
}) {
  if (name === "visitor_type") {
    return (
      <ChoiceGroup
        label={label}
        value={value}
        options={visitorTypes}
        labels={pt.registration.visitorTypes}
        onChange={onChange}
      />
    )
  }
  return (
    <ChoiceGroup
      label={label}
      value={value}
      options={visitReasons}
      labels={pt.registration.visitReasons}
      onChange={onChange}
    />
  )
}

/**
 * Chips de escolha única (`ToggleGroup` com `type="single"`), com o
 * rótulo do campo como nome do grupo.
 */
function ChoiceGroup<T extends string>({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string
  value: string
  options: readonly T[]
  labels: Record<T, string>
  onChange: (value: string) => void
}) {
  return (
    <Field>
      <p className="text-label text-foreground">{label}</p>
      <ToggleGroup
        type="single"
        value={value}
        aria-label={label}
        onValueChange={onChange}
      >
        {options.map((option) => (
          <ToggleGroupItem key={option} value={option}>
            {labels[option]}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </Field>
  )
}

// O navegador sugere nome, e-mail e telefone; nos outros campos, não.
function autoCompleteFor(name: FieldName) {
  if (name === "full_name") {
    return "name"
  }
  if (name === "email") {
    return "email"
  }
  if (name === "phone") {
    return "tel"
  }
  return "off"
}
