/**
 * Tela `/attendance/commitment`: o compromisso de confidencialidade da
 * equipe, antes de assumir o primeiro atendimento (seção 29.3).
 *
 * View: recebe a versão vigente e a ação de aceitar de
 * `app/routes/attendance-commitment.tsx`. Mostra os dez itens do
 * compromisso, a caixa "Li e aceito o compromisso" e o botão Aceitar e
 * continuar, que só libera com a caixa marcada. O aceite fica gravado em
 * `attendant_acknowledgements` com a versão.
 */
import { useId, useState } from "react"

import { PageHeading } from "@/app/page-heading.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Checkbox } from "@/components/ui/checkbox.tsx"
import { Field, FieldContent } from "@/components/ui/field.tsx"
import { Label } from "@/components/ui/label.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { pt } from "@/i18n/pt.ts"

/** A tela do compromisso. */
export function CommitmentScreen({
  version,
  pending,
  error,
  onAccept,
}: {
  version: string | null
  pending: boolean
  error: string | null
  onAccept: () => void
}) {
  const [checked, setChecked] = useState(false)
  const id = useId()
  const t = pt.attendance.commitment
  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col gap-6">
      <PageHeading title={pt.pages.attendanceCommitment} />
      <p className="text-body text-foreground">
        {t.lead.replace("{version}", version ?? "—")}
      </p>
      <ol className="m-0 flex list-decimal flex-col gap-2 pl-6 text-body text-foreground">
        {t.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ol>
      <Field orientation="horizontal">
        <Checkbox
          id={id}
          checked={checked}
          disabled={pending}
          onCheckedChange={(next) => {
            setChecked(next === true)
          }}
        />
        <FieldContent>
          <Label htmlFor={id} className="max-md:min-h-11">
            {t.checkbox}
          </Label>
        </FieldContent>
      </Field>
      {error ? (
        <p role="alert" className="text-body text-danger">
          {error}
        </p>
      ) : null}
      <div>
        <Button
          type="button"
          disabled={!checked || pending || !version}
          onClick={onAccept}
        >
          {pending ? (
            <Spinner aria-hidden="true" data-icon="inline-start" />
          ) : null}
          {pending ? t.accepting : t.accept}
        </Button>
      </div>
    </div>
  )
}
