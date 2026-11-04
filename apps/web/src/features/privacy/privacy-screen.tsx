import { useEffect, useState, type ReactNode } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm, useWatch } from "react-hook-form"
import { useLocation } from "react-router"

import { PageHeading } from "@/app/page-heading.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { Button } from "@/components/ui/button.tsx"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field.tsx"
import { Input } from "@/components/ui/input.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { Textarea } from "@/components/ui/textarea.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"

import {
  emptyRequest,
  noticeSections,
  requestSchema,
  requestTypes,
  sentMessage,
  type RequestValues,
} from "./model.ts"
import type { SubmitResult } from "./usePrivacyRequest.ts"

const notice = pt.privacyNotice.sections

export function PrivacyScreen({
  version,
  contactEmail,
  email,
  submit,
}: {
  version: string | null
  contactEmail: string | null
  email: string | null
  submit: (values: RequestValues) => Promise<SubmitResult>
}) {
  const location = useLocation()

  useEffect(() => {
    const id = location.hash.slice(1)
    if (id) {
      document.getElementById(id)?.scrollIntoView()
    }
  }, [location.hash])

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8">
      <div className="flex flex-col gap-2">
        <PageHeading title={pt.pages.privacy} />
        {version ? (
          <p className="text-label text-muted-foreground">
            {pt.privacyNotice.version.replace("{version}", version)}
          </p>
        ) : null}
        <p className="text-body text-foreground">{pt.privacyNotice.fictional}</p>
      </div>

      <nav aria-label={pt.privacyNotice.contentsLabel}>
        <ul className="flex flex-wrap gap-2">
          {noticeSections.map((section) => (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                className="inline-flex min-h-11 items-center rounded-full bg-card px-4 text-body text-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring md:min-h-8"
              >
                {notice[section.key].title}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <NoticeSection id="quem-cuida" title={notice.controller.title}>
        <Paragraphs items={notice.controller.body} />
        <p className="text-body text-foreground">
          {contactEmail
            ? notice.controller.contact.replace("{email}", contactEmail)
            : notice.controller.contactMissing}
        </p>
      </NoticeSection>

      <NoticeSection id="dados" title={notice.data.title}>
        <NoticeTable columns={notice.data.columns} rows={notice.data.rows} />
      </NoticeSection>

      <NoticeSection id="saude" title={notice.health.title}>
        <Paragraphs items={notice.health.body} />
      </NoticeSection>

      <NoticeSection id="compartilhamento" title={notice.processors.title}>
        <p className="text-body text-foreground">{notice.processors.lead}</p>
        <NoticeTable
          columns={notice.processors.columns}
          rows={notice.processors.rows}
        />
      </NoticeSection>

      <NoticeSection id="retencao" title={notice.retention.title}>
        <NoticeTable
          columns={notice.retention.columns}
          rows={notice.retention.rows}
        />
      </NoticeSection>

      <NoticeSection id="direitos" title={notice.rights.title}>
        <Paragraphs items={notice.rights.body} />
      </NoticeSection>

      <NoticeSection id="cookies" title={notice.cookies.title}>
        <p className="text-body text-foreground">{notice.cookies.lead}</p>
        <NoticeTable columns={notice.cookies.columns} rows={notice.cookies.rows} />
        <p className="text-body text-foreground">{notice.cookies.storage}</p>
      </NoticeSection>

      <NoticeSection id="seguranca" title={notice.security.title}>
        <Paragraphs items={notice.security.body} />
      </NoticeSection>

      <NoticeSection id="incidentes" title={notice.incidents.title}>
        <Paragraphs items={notice.incidents.body} />
      </NoticeSection>

      <NoticeSection id="pedidos" title={notice.channel.title}>
        <p className="text-body text-foreground">{notice.channel.lead}</p>
        <RequestForm email={email} submit={submit} />
      </NoticeSection>
    </div>
  )
}

function NoticeSection({
  id,
  title,
  children,
}: {
  id: string
  title: string
  children: ReactNode
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className="flex scroll-mt-6 flex-col gap-3"
    >
      <h2 id={`${id}-title`} className="text-title text-foreground-strong">
        {title}
      </h2>
      {children}
    </section>
  )
}

function Paragraphs({ items }: { items: readonly string[] }) {
  return (
    <>
      {items.map((item) => (
        <p key={item} className="text-body text-foreground">
          {item}
        </p>
      ))}
    </>
  )
}

function NoticeTable({
  columns,
  rows,
}: {
  columns: readonly string[]
  rows: readonly (readonly string[])[]
}) {
  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-border">
      <table className="w-full border-collapse text-left text-body text-foreground">
        <thead className="bg-card">
          <tr>
            {columns.map((column) => (
              <th key={column} scope="col" className="p-3 text-label">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row[0]} className="border-t border-border">
              {row.map((cell, index) =>
                index === 0 ? (
                  <th key={cell} scope="row" className="p-3 font-medium">
                    {cell}
                  </th>
                ) : (
                  <td key={cell} className="p-3">
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const requestFields = ["contact_email", "request_type", "description"] as const

function RequestForm({
  email,
  submit,
}: {
  email: string | null
  submit: (values: RequestValues) => Promise<SubmitResult>
}) {
  const [pending, setPending] = useState(false)
  const [sent, setSent] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)
  const form = useForm<RequestValues>({
    resolver: zodResolver(requestSchema),
    defaultValues: emptyRequest(email),
    values: emptyRequest(email),
  })
  const errors = form.formState.errors
  const requestType = useWatch({ control: form.control, name: "request_type" })

  async function send(values: RequestValues) {
    setPending(true)
    setSent(null)
    setFormError(null)
    setRequestId(null)
    try {
      const result = await submit(values)
      if (result.ok) {
        setSent(sentMessage(result.dueAt))
        form.reset(emptyRequest(email))
        return
      }
      let known = false
      for (const [field, message] of Object.entries(result.fieldErrors)) {
        const name = requestFields.find((item) => item === field)
        if (name) {
          form.setError(name, { message })
          known = true
        }
      }
      setRequestId(result.requestId)
      if (!known) {
        setFormError(result.message)
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <form
      aria-labelledby="pedidos-title"
      className="flex flex-col gap-6"
      noValidate
      onSubmit={(event) => {
        void form.handleSubmit(send)(event)
      }}
    >
      <FieldGroup>
        <Field data-invalid={errors.contact_email ? true : undefined}>
          <FieldLabel htmlFor="request-email">
            {pt.privacyRequest.email}
          </FieldLabel>
          <Input
            id="request-email"
            type="email"
            autoComplete="email"
            disabled={pending}
            aria-invalid={errors.contact_email ? true : undefined}
            aria-describedby={
              errors.contact_email ? "request-email-error" : undefined
            }
            className="h-11 md:h-8"
            {...form.register("contact_email")}
          />
          {errors.contact_email ? (
            <FieldError id="request-email-error">
              {errors.contact_email.message}
            </FieldError>
          ) : null}
        </Field>
        <Field data-invalid={errors.request_type ? true : undefined}>
          <p className="text-label text-foreground">{pt.privacyRequest.type}</p>
          <ToggleGroup
            type="single"
            value={requestType}
            aria-label={pt.privacyRequest.type}
            onValueChange={(value) =>
              form.setValue("request_type", value, {
                shouldValidate: form.formState.isSubmitted,
              })
            }
          >
            {requestTypes.map((type) => (
              <ToggleGroupItem key={type} value={type} disabled={pending}>
                {pt.privacyRequest.types[type]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          {errors.request_type ? (
            <FieldError>{errors.request_type.message}</FieldError>
          ) : null}
        </Field>
        <Field data-invalid={errors.description ? true : undefined}>
          <FieldLabel htmlFor="request-description">
            {pt.privacyRequest.description}
          </FieldLabel>
          <Textarea
            id="request-description"
            rows={5}
            disabled={pending}
            aria-invalid={errors.description ? true : undefined}
            aria-describedby={
              errors.description
                ? "request-description-hint request-description-error"
                : "request-description-hint"
            }
            {...form.register("description")}
          />
          <FieldDescription id="request-description-hint">
            {pt.privacyRequest.descriptionHint}
          </FieldDescription>
          {errors.description ? (
            <FieldError id="request-description-error">
              {errors.description.message}
            </FieldError>
          ) : null}
        </Field>
      </FieldGroup>
      {formError ? (
        <p role="alert" className="text-body text-danger">
          {formError}
        </p>
      ) : null}
      {requestId ? <RequestIdCopy requestId={requestId} /> : null}
      {sent ? (
        <p role="status" className="text-body text-foreground">
          {sent}
        </p>
      ) : null}
      <Button
        type="submit"
        className="min-h-11 w-fit md:min-h-8"
        disabled={pending}
      >
        {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
        {pending ? pt.privacyRequest.submitting : pt.privacyRequest.submit}
      </Button>
    </form>
  )
}
