import { PanelRightClose, PanelRightOpen, SendHorizontal } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"
import { Link } from "react-router"

import { PageHeading } from "@/app/page-heading.tsx"
import { AssistantBubble } from "@/components/patterns/assistant-bubble.tsx"
import { ChatErrorNotice } from "@/components/patterns/chat-error-notice.tsx"
import { ConsentFieldSet } from "@/components/patterns/consent-field-set.tsx"
import { PasswordCard } from "@/components/patterns/password-card.tsx"
import { ProfileSummaryCard } from "@/components/patterns/profile-summary-card.tsx"
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
  emailOffersSignIn,
  type Consents,
  type RegistrationSession,
} from "@/features/registration/model.ts"
import { useRegistrationChat } from "@/features/registration/useRegistrationChat.ts"

type Chat = ReturnType<typeof useRegistrationChat>

export function RegistrationScreen({
  session,
  loading,
  pending,
  notice,
  outgoing,
  dismissNotice,
  actionErrors,
  send,
  skip,
  editField,
  setPassword,
  review,
  accept,
}: Chat) {
  const { isDesktop } = useMotion()
  const [draft, setDraft] = useState("")
  const summaryId = useId()
  const [summaryOpen, setSummaryOpen] = useState(false)
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

  async function sendDraft(text: string) {
    const sent = await send(text)
    if (sent) {
      setDraft("")
    }
  }

  const retryText = notice?.retryText ?? null

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6">
      <PageHeading title={pt.pages.register} />
      <p className="max-w-[760px] text-body text-foreground">
        {pt.registration.lead}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          className="min-h-11 md:min-h-8"
          aria-expanded={summaryOpen}
          aria-controls={summaryId}
          onClick={() => setSummaryOpen((open) => !open)}
        >
          {summaryOpen ? (
            <PanelRightClose data-icon="inline-start" aria-hidden="true" />
          ) : (
            <PanelRightOpen data-icon="inline-start" aria-hidden="true" />
          )}
          {summaryOpen
            ? pt.registration.summaryHide
            : pt.registration.summaryShow.replace(
                "{count}",
                String(filledFieldCount(session?.fields ?? emptySummaryFields()))
              )}
        </Button>
        <Button asChild variant="link" className="h-11 px-0 md:h-8">
          <Link to={formPath(session?.id ?? null)}>
            {pt.registration.useForm}
          </Link>
        </Button>
      </div>
      <div className="flex flex-1 flex-col gap-4 lg:flex-row lg:items-start">
        {summaryOpen && !isDesktop ? <div id={summaryId}>{summary}</div> : null}
        <section
          aria-label={pt.registration.thread}
          className="flex min-w-0 flex-1 flex-col rounded-2xl border border-border bg-shell"
        >
          <div className="flex flex-1 flex-col gap-4 p-4 md:p-5">
            {loading ? <AssistantBubble typing /> : null}
            {session ? (
              <Transcript
                session={session}
                outgoing={outgoing}
                typing={pending && outgoing !== null}
              />
            ) : null}
            {notice ? (
              <ChatErrorNotice
                title={pt.registration.errorTitle}
                message={notice.message}
                requestId={notice.requestId}
                onDismiss={session ? dismissNotice : undefined}
                onRetry={
                  retryText && !pending
                    ? () => {
                        void sendDraft(retryText)
                      }
                    : undefined
                }
              >
                {notice.unavailable || !session ? (
                  <Button asChild variant="link" className="h-11 px-0 md:h-8">
                    <Link to={formPath(session?.id ?? null)}>
                      {pt.registration.useForm}
                    </Link>
                  </Button>
                ) : null}
              </ChatErrorNotice>
            ) : null}
          </div>
          {session ? (
            <div className="sticky bottom-0 z-10 rounded-b-2xl border-t border-border bg-shell p-4 md:p-5">
              <StepPanel
                session={session}
                pending={pending}
                draft={draft}
                onDraftChange={setDraft}
                actionErrors={actionErrors}
                send={sendDraft}
                skip={skip}
                setPassword={setPassword}
                review={review}
                accept={accept}
              />
            </div>
          ) : null}
        </section>
        {summaryOpen && isDesktop ? (
          <div id={summaryId} className="sticky top-0 w-80 shrink-0">
            {summary}
          </div>
        ) : null}
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

function Transcript({
  session,
  outgoing,
  typing,
}: {
  session: RegistrationSession
  outgoing: string | null
  typing: boolean
}) {
  const endRef = useRef<HTMLDivElement>(null)
  const latest = [...session.messages]
    .reverse()
    .find((message) => message.role === "assistant")
  const count = session.messages.length

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end", behavior: "smooth" })
  }, [count, typing])

  return (
    <div className="flex flex-col gap-4">
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {typing ? pt.registration.typing : (latest?.text ?? "")}
      </div>
      <ol className="m-0 flex list-none flex-col gap-4 p-0">
        {session.messages.map((message, index) => (
          <li key={`${message.created_at}-${index}`}>
            {message.role === "user" ? (
              <UserMessage text={message.text} privacy={false} />
            ) : (
              <AssistantBubble text={message.text} />
            )}
          </li>
        ))}
        {!typing && emailOffersSignIn(session.field_errors.email) ? (
          <li className="flex flex-wrap gap-2 ps-10">
            <Button asChild className="min-h-11 md:min-h-8">
              <Link to="/sign-in">{pt.registration.signIn}</Link>
            </Button>
          </li>
        ) : null}
        {outgoing ? (
          <li>
            <UserMessage text={outgoing} privacy={false} />
          </li>
        ) : null}
        {typing ? (
          <li>
            <AssistantBubble typing />
          </li>
        ) : null}
      </ol>
      <div ref={endRef} />
    </div>
  )
}

function StepPanel({
  session,
  pending,
  draft,
  onDraftChange,
  actionErrors,
  send,
  skip,
  setPassword,
  review,
  accept,
}: {
  session: RegistrationSession
  pending: boolean
  draft: string
  onDraftChange: (value: string) => void
  actionErrors: Record<string, string>
  send: (text: string) => Promise<void>
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
      pending={pending}
      value={draft}
      onChange={onDraftChange}
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
  value,
  onChange,
  canSkip,
  onSend,
  onSkip,
}: {
  pending: boolean
  value: string
  onChange: (value: string) => void
  canSkip: boolean
  onSend: (text: string) => Promise<void>
  onSkip: () => void
}) {
  const fieldId = useId()
  const hintId = useId()
  const fieldRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const field = fieldRef.current
    if (!field) {
      return
    }
    field.style.height = "auto"
    field.style.height = `${field.scrollHeight}px`
  }, [value])

  function submit() {
    const text = value.trim()
    if (!text || pending) {
      return
    }
    void onSend(text)
  }

  return (
    <form
      aria-label={pt.registration.replyForm}
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <Field data-disabled={pending || undefined}>
        <FieldLabel htmlFor={fieldId} className="sr-only">
          {pt.registration.messageLabel}
        </FieldLabel>
        <div className="flex items-end gap-2 rounded-2xl border border-border-strong bg-background p-2 focus-within:border-ring">
          <Textarea
            ref={fieldRef}
            id={fieldId}
            value={value}
            rows={1}
            maxLength={1000}
            placeholder={pt.registration.messagePlaceholder}
            disabled={pending}
            aria-describedby={canSkip ? hintId : undefined}
            className="max-h-40 min-h-11 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 md:min-h-8"
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault()
                submit()
              }
            }}
          />
          <Button
            type="submit"
            className="min-h-11 shrink-0 md:min-h-8"
            disabled={pending || value.trim() === ""}
            aria-busy={pending || undefined}
          >
            {pending ? (
              <Spinner aria-hidden data-icon="inline-start" />
            ) : (
              <SendHorizontal data-icon="inline-start" aria-hidden="true" />
            )}
            {pending ? pt.registration.sending : pt.registration.send}
          </Button>
        </div>
      </Field>
      {canSkip ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <FieldDescription id={hintId}>
            {pt.registration.optionalHint}
          </FieldDescription>
          <Button
            type="button"
            variant="outline"
            className="min-h-11 md:min-h-8"
            disabled={pending}
            onClick={onSkip}
          >
            {pt.registration.skip}
          </Button>
        </div>
      ) : null}
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
