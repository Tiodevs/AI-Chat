import { useId, useState, type ReactNode } from "react"
import { Link } from "react-router"

import { PageHeading } from "@/app/page-heading.tsx"
import { ConsentFieldSet } from "@/components/patterns/consent-field-set.tsx"
import { PasswordCard } from "@/components/patterns/password-card.tsx"
import { ProfileSummaryCard } from "@/components/patterns/profile-summary-card.tsx"
import { RegistrationStepper } from "@/components/patterns/registration-stepper.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { UserMessage } from "@/components/patterns/user-message.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { Textarea } from "@/components/ui/textarea.tsx"
import { pt } from "@/i18n/pt.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import {
  canSkipStep,
  consentIssues,
  emptyConsents,
  filledFieldCount,
  formPath,
  phaseForStep,
  type Consents,
  type RegistrationSession,
} from "@/features/registration/model.ts"
import { useRegistrationChat } from "@/features/registration/useRegistrationChat.ts"

type Chat = ReturnType<typeof useRegistrationChat>

export function RegistrationScreen({
  session,
  loading,
  pending,
  error,
  requestId,
  actionErrors,
  send,
  skip,
  editField,
  setPassword,
  review,
  accept,
}: Chat) {
  const { isDesktop } = useMotion()
  const phase = phaseForStep(session?.next_step ?? "full_name")
  const summary = session ? (
    <ProfileSummaryCard
      fields={session.fields}
      fieldErrors={session.field_errors}
      pending={pending}
      onEdit={editField}
    />
  ) : (
    <SummarySkeleton />
  )

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <PageHeading title={pt.pages.register} />
      <p className="max-w-[760px] text-body text-foreground">
        {pt.registration.lead}
      </p>
      <div className="sticky top-0 z-10 flex justify-end bg-background py-2">
        <Button asChild variant="link" className="h-11 px-0 md:h-8">
          <Link to={formPath(session?.id ?? null)}>
            {pt.registration.useForm}
          </Link>
        </Button>
      </div>
      <RegistrationStepper phase={phase} />
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {isDesktop ? null : (
          <MobileSummary
            count={filledFieldCount(session?.fields ?? emptySummaryFields())}
          >
            {summary}
          </MobileSummary>
        )}
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          {loading ? <TranscriptSkeleton /> : null}
          {session ? <Transcript session={session} /> : null}
          {error ? (
            <p role="alert" className="text-body text-danger">
              {error}
            </p>
          ) : null}
          {requestId ? <RequestIdCopy requestId={requestId} /> : null}
          {session ? (
            <StepPanel
              session={session}
              pending={pending}
              actionErrors={actionErrors}
              send={send}
              skip={skip}
              setPassword={setPassword}
              review={review}
              accept={accept}
            />
          ) : null}
        </div>
        {isDesktop ? <div className="w-80 shrink-0">{summary}</div> : null}
      </div>
    </div>
  )
}

function emptySummaryFields() {
  return {
    full_name: null,
    email: null,
    phone: null,
    visitor_type: null,
    visit_reason: null,
  }
}

function MobileSummary({
  count,
  children,
}: {
  count: number
  children: ReactNode
}) {
  const [open, setOpen] = useState(true)
  const panelId = useId()
  return (
    <div className="flex flex-col gap-2">
      <Button
        type="button"
        variant="outline"
        className="min-h-11 justify-between md:min-h-8"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        {pt.registration.summaryToggle.replace("{count}", String(count))}
      </Button>
      {open ? <div id={panelId}>{children}</div> : null}
    </div>
  )
}

function Transcript({ session }: { session: RegistrationSession }) {
  const latest = [...session.messages]
    .reverse()
    .find((message) => message.role === "assistant")
  return (
    <div className="flex flex-col gap-4" aria-label={pt.registration.thread}>
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {latest?.text ?? ""}
      </div>
      <ol className="m-0 flex list-none flex-col gap-4 p-0">
        {session.messages.map((message, index) => (
          <li key={`${message.created_at}-${index}`}>
            {message.role === "user" ? (
              <UserMessage text={message.text} privacy={false} />
            ) : (
              <p className="max-w-[85%] text-message text-foreground">
                {message.text}
              </p>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}

function StepPanel({
  session,
  pending,
  actionErrors,
  send,
  skip,
  setPassword,
  review,
  accept,
}: {
  session: RegistrationSession
  pending: boolean
  actionErrors: Record<string, string>
  send: Chat["send"]
  skip: Chat["skip"]
  setPassword: Chat["setPassword"]
  review: Chat["review"]
  accept: Chat["accept"]
}) {
  if (session.next_step === "password") {
    return (
      <PasswordStep
        pending={pending}
        error={session.field_errors.password ?? null}
        onSubmit={setPassword}
      />
    )
  }
  if (session.next_step === "review") {
    return <ReviewStep pending={pending} onReview={review} />
  }
  if (session.next_step === "acceptance") {
    return (
      <AcceptStep
        pending={pending}
        serverErrors={actionErrors}
        onAccept={accept}
      />
    )
  }
  return (
    <ReplyStep
      key={session.next_step}
      pending={pending}
      canSkip={canSkipStep(session.next_step)}
      onSend={send}
      onSkip={() => {
        void skip()
      }}
    />
  )
}

function ReplyStep({
  pending,
  canSkip,
  onSend,
  onSkip,
}: {
  pending: boolean
  canSkip: boolean
  onSend: (text: string) => Promise<boolean>
  onSkip: () => void
}) {
  const fieldId = useId()
  const [value, setValue] = useState("")

  async function submit() {
    const text = value.trim()
    if (!text) {
      return
    }
    const sent = await onSend(text)
    if (sent) {
      setValue("")
    }
  }

  return (
    <form
      aria-label={pt.registration.replyForm}
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        void submit()
      }}
    >
      <Field data-disabled={pending || undefined}>
        <FieldLabel htmlFor={fieldId}>
          {pt.registration.messageLabel}
        </FieldLabel>
        <Textarea
          id={fieldId}
          value={value}
          rows={2}
          maxLength={1000}
          placeholder={pt.registration.messagePlaceholder}
          disabled={pending}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault()
              void submit()
            }
          }}
        />
        {canSkip ? (
          <FieldDescription>{pt.registration.optionalHint}</FieldDescription>
        ) : null}
      </Field>
      <div className="flex flex-wrap justify-end gap-2">
        {canSkip ? (
          <Button
            type="button"
            variant="outline"
            className="min-h-11 md:min-h-8"
            disabled={pending}
            onClick={onSkip}
          >
            {pt.registration.skip}
          </Button>
        ) : null}
        <Button
          type="submit"
          className="min-h-11 md:min-h-8"
          disabled={pending || value.trim() === ""}
        >
          {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
          {pending ? pt.registration.sending : pt.registration.send}
        </Button>
      </div>
    </form>
  )
}

function PasswordStep({
  pending,
  error,
  onSubmit,
}: {
  pending: boolean
  error: string | null
  onSubmit: (password: string) => Promise<void>
}) {
  const [password, setPassword] = useState("")
  return (
    <PasswordCard
      value={password}
      onChange={setPassword}
      pending={pending}
      error={error}
      moveFocus
      onSubmit={() => {
        void onSubmit(password)
      }}
    />
  )
}

function ReviewStep({
  pending,
  onReview,
}: {
  pending: boolean
  onReview: (accept: boolean) => Promise<void>
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        type="button"
        className="min-h-11 md:min-h-8"
        disabled={pending}
        onClick={() => {
          void onReview(true)
        }}
      >
        {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
        {pt.registration.confirm}
      </Button>
      <Button
        type="button"
        variant="outline"
        className="min-h-11 md:min-h-8"
        disabled={pending}
        onClick={() => {
          void onReview(false)
        }}
      >
        {pt.registration.correct}
      </Button>
    </div>
  )
}

function AcceptStep({
  pending,
  serverErrors,
  onAccept,
}: {
  pending: boolean
  serverErrors: Record<string, string>
  onAccept: (consents: Consents) => Promise<void>
}) {
  const [value, setValue] = useState(emptyConsents)
  const [errors, setErrors] = useState(consentIssues(emptyConsents()))
  const [showErrors, setShowErrors] = useState(false)
  const merged = {
    accept_terms:
      serverErrors.accept_terms ??
      (showErrors ? errors.accept_terms : undefined),
    age_18_plus:
      serverErrors.age_18_plus ?? (showErrors ? errors.age_18_plus : undefined),
  }

  return (
    <form
      aria-label={pt.registration.consentsTitle}
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        const issues = consentIssues(value)
        setErrors(issues)
        if (issues.accept_terms || issues.age_18_plus) {
          setShowErrors(true)
          return
        }
        void onAccept(value)
      }}
    >
      <ConsentFieldSet
        value={value}
        disabled={pending}
        errors={merged}
        onChange={(next) => {
          setValue(next)
          setErrors(consentIssues(next))
        }}
      />
      <Button
        type="submit"
        className="min-h-11 w-fit md:min-h-8"
        disabled={pending}
      >
        {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
        {pending ? pt.registration.creating : pt.registration.createAccount}
      </Button>
    </form>
  )
}

function SummarySkeleton() {
  return <Skeleton className="h-40 w-full" />
}

function TranscriptSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-6 w-1/2" />
    </div>
  )
}
