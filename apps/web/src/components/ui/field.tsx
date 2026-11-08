/**
 * Peças de formulário do shadcn/ui: `FieldSet`, `FieldGroup`, `Field`,
 * rótulo, descrição e erro. São marcação e classes; só o `FieldLabel`
 * usa o Radix, pelo `Label`.
 *
 * A seção 14.8 manda os formulários usarem `FieldGroup` e `Field`, com
 * `aria-invalid` no controle. Aparecem no `Composer`, no `PasswordCard`,
 * no `ConsentFieldSet`, no `ProfileSummaryCard` e nos formulários das
 * telas: entrar, cadastro, conta, privacidade e admin.
 *
 * O estado chega por atributo no `Field`: `data-invalid` pinta o texto de
 * `--danger`, e `data-disabled` esmaece o rótulo. Quem liga o controle à
 * dica e ao erro é o chamador, com `id` e `aria-describedby`. As cores vêm
 * de `text-destructive` e `text-muted-foreground`, que `tokens.css` liga a
 * `--danger` e `--muted-foreground`. Seção 14.6.
 */
import { useMemo } from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

import { Label } from "@/components/ui/label.tsx"
import { Separator } from "@/components/ui/separator.tsx"

/**
 * `<fieldset>` que agrupa campos relacionados. O `disabled` nativo do
 * `fieldset` desabilita todos os controles de dentro, como no
 * `ConsentFieldSet` durante o envio.
 */
function FieldSet({ className, ...props }: React.ComponentProps<"fieldset">) {
  return (
    <fieldset
      data-slot="field-set"
      className={cn(
        "flex flex-col gap-4 has-[>[data-slot=checkbox-group]]:gap-3 has-[>[data-slot=radio-group]]:gap-3",
        className,
      )}
      {...props}
    />
  )
}

/**
 * Legenda do `fieldset`. O leitor de tela a lê ao entrar no grupo.
 * `variant="label"` usa o tamanho de rótulo, em vez do de título.
 */
function FieldLegend({
  className,
  variant = "legend",
  ...props
}: React.ComponentProps<"legend"> & { variant?: "legend" | "label" }) {
  return (
    <legend
      data-slot="field-legend"
      data-variant={variant}
      className={cn(
        "mb-1.5 font-medium data-[variant=label]:text-sm data-[variant=legend]:text-base",
        className,
      )}
      {...props}
    />
  )
}

/**
 * Pilha de campos com `gap`, sem `space-y` (seção 14.8). É um contêiner
 * `@container`, que a orientação `responsive` do `Field` consulta.
 */
function FieldGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field-group"
      className={cn(
        "group/field-group @container/field-group flex w-full flex-col gap-5 data-[slot=checkbox-group]:gap-3 *:data-[slot=field-group]:gap-4",
        className,
      )}
      {...props}
    />
  )
}

/**
 * Orientação do `Field` por `cva`:
 * - `vertical` (padrão): rótulo em cima e controle embaixo.
 * - `horizontal`: controle e rótulo na mesma linha, como a caixa do
 *   `ConsentFieldSet` e o interruptor da conta.
 * - `responsive`: vertical até o `FieldGroup` chegar à largura `@md`, e
 *   horizontal daí em diante. Sem uso nas telas.
 */
const fieldVariants = cva(
  "group/field flex w-full gap-2 data-[invalid=true]:text-destructive",
  {
    variants: {
      orientation: {
        vertical: "flex-col *:w-full [&>.sr-only]:w-auto",
        horizontal:
          "flex-row items-center has-[>[data-slot=field-content]]:items-start *:data-[slot=field-label]:flex-auto has-[>[data-slot=field-content]]:[&>[role=checkbox],[role=radio]]:mt-px",
        responsive:
          "flex-col *:w-full @md/field-group:flex-row @md/field-group:items-center @md/field-group:*:w-auto @md/field-group:has-[>[data-slot=field-content]]:items-start @md/field-group:*:data-[slot=field-label]:flex-auto [&>.sr-only]:w-auto @md/field-group:has-[>[data-slot=field-content]]:[&>[role=checkbox],[role=radio]]:mt-px",
      },
    },
    defaultVariants: {
      orientation: "vertical",
    },
  },
)

/**
 * Um campo: `role="group"` junta rótulo, controle, dica e erro. Passe
 * `data-invalid` com o erro e `data-disabled` com o controle desabilitado.
 */
function Field({
  className,
  orientation = "vertical",
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof fieldVariants>) {
  return (
    <div
      role="group"
      data-slot="field"
      data-orientation={orientation}
      className={cn(fieldVariants({ orientation }), className)}
      {...props}
    />
  )
}

/** Coluna de rótulo, descrição e erro ao lado da caixa ou do interruptor. */
function FieldContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field-content"
      className={cn(
        "group/field-content flex flex-1 flex-col gap-0.5 leading-snug",
        className,
      )}
      {...props}
    />
  )
}

/**
 * Rótulo do campo, sobre o `Label`. O `htmlFor` liga o rótulo ao controle.
 * Com uma caixa marcada dentro dele, ganha borda e fundo de `--primary`
 * (`has-data-checked`), um uso do shadcn que o projeto não faz.
 */
function FieldLabel({ className, ...props }: React.ComponentProps<typeof Label>) {
  return (
    <Label
      data-slot="field-label"
      className={cn(
        "group/field-label peer/field-label flex w-fit gap-2 leading-snug group-data-[disabled=true]/field:opacity-50",
        "has-data-checked:border-primary/30 has-data-checked:bg-primary/5",
        "has-[>[data-slot=field]]:w-full has-[>[data-slot=field]]:flex-col has-[>[data-slot=field]]:rounded-lg has-[>[data-slot=field]]:border",
        className,
      )}
      {...props}
    />
  )
}

/** Título sem `<label>`, com a aparência do rótulo. Sem uso nas telas. */
function FieldTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field-label"
      className={cn(
        "flex w-fit items-center gap-2 text-sm font-medium group-data-[disabled=true]/field:opacity-50",
        className,
      )}
      {...props}
    />
  )
}

/**
 * Dica do campo, em `--muted-foreground`. O chamador põe o `id` dela no
 * `aria-describedby` do controle, para o leitor de tela lê-la junto.
 */
function FieldDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="field-description"
      className={cn(
        "text-left text-sm leading-normal font-normal text-muted-foreground group-has-data-horizontal/field:text-balance",
        "[[data-variant=legend]+&]:-mt-1.5 last:mt-0 nth-last-2:-mt-1",
        "[&>a]:underline [&>a]:underline-offset-4 [&>a:hover]:text-primary",
        className,
      )}
      {...props}
    />
  )
}

/** Divisor entre campos, com um texto opcional no meio. Sem uso nas telas. */
function FieldSeparator({
  children,
  className,
  ...props
}: React.ComponentProps<"div"> & {
  children?: React.ReactNode
}) {
  return (
    <div
      data-slot="field-separator"
      data-content={!!children}
      className={cn(
        "relative -my-2 h-5 text-sm group-data-[variant=outline]/field-group:-mb-2",
        className,
      )}
      {...props}
    >
      <Separator className="absolute inset-0 top-1/2" />
      {children ? (
        <span
          className="relative mx-auto block w-fit bg-background px-2 text-muted-foreground"
          data-slot="field-separator-content"
        >
          {children}
        </span>
      ) : null}
    </div>
  )
}

/**
 * Mensagem de erro do campo, com `role="alert"`: o leitor de tela a
 * anuncia quando ela aparece. O texto é `--danger`, e o controle marca
 * `aria-invalid`, então o erro não depende só da cor (seção 15.8).
 *
 * Recebe o texto em `children` ou a lista `errors`, no formato do React
 * Hook Form; as telas só usam `children`. Sem conteúdo, não renderiza.
 */
function FieldError({
  className,
  children,
  errors,
  ...props
}: React.ComponentProps<"div"> & {
  errors?: Array<{ message?: string } | undefined>
}) {
  const content = useMemo(() => {
    if (children) {
      return children
    }
    if (!errors?.length) {
      return null
    }
    // O `Map` pela mensagem tira as repetidas e mantém a ordem. Uma vira
    // texto; várias viram lista.
    const uniqueErrors = [
      ...new Map(errors.map((error) => [error?.message, error])).values(),
    ]
    const first = uniqueErrors[0]
    if (uniqueErrors.length === 1) {
      return first?.message
    }
    return (
      <ul className="ml-4 flex list-disc flex-col gap-1">
        {uniqueErrors.map((error) =>
          error?.message ? <li key={error.message}>{error.message}</li> : null,
        )}
      </ul>
    )
  }, [children, errors])

  if (!content) {
    return null
  }

  return (
    <div
      role="alert"
      data-slot="field-error"
      className={cn("text-sm font-normal text-destructive", className)}
      {...props}
    >
      {content}
    </div>
  )
}

export {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSeparator,
  FieldSet,
  FieldTitle,
}
