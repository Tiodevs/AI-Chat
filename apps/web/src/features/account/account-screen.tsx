import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm, useWatch } from "react-hook-form"
import { Link } from "react-router"

import { PageHeading } from "@/app/page-heading.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog.tsx"
import { Button } from "@/components/ui/button.tsx"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field.tsx"
import { Input } from "@/components/ui/input.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { Switch } from "@/components/ui/switch.tsx"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"
import { useMotion, type MotionPreference } from "@/motion/MotionProvider.tsx"

import {
  consentFor,
  deleteConfirmed,
  formatDate,
  grantedOn,
  isGranted,
  personalizationPurpose,
  profileDefaults,
  profileSchema,
  qualityPurpose,
  termsPurpose,
  visitReasons,
  visitorTypes,
  type OptionalPurpose,
  type ProfileValues,
  type SubmitFailure,
} from "./model.ts"
import type { AccountModel } from "./useAccount.ts"

const profileFields = [
  "full_name",
  "phone",
  "visitor_type",
  "visit_reason",
] as const

const motionOptions: { value: MotionPreference; label: string }[] = [
  { value: "system", label: pt.profile.motionSystem },
  { value: "on", label: pt.profile.motionReduce },
  { value: "off", label: pt.profile.motionAllow },
]

export function AccountScreen(model: AccountModel) {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <PageHeading title={pt.pages.account} />
      <Tabs defaultValue="profile">
        <TabsList aria-label={pt.account.tabsLabel}>
          <TabsTrigger value="profile">{pt.account.tabs.profile}</TabsTrigger>
          <TabsTrigger value="conversations">
            {pt.account.tabs.conversations}
          </TabsTrigger>
          <TabsTrigger value="privacy">{pt.account.tabs.privacy}</TabsTrigger>
        </TabsList>
        <TabsContent value="profile">
          <ProfileTab {...model} />
        </TabsContent>
        <TabsContent value="conversations">
          <ConversationsTab {...model} />
        </TabsContent>
        <TabsContent value="privacy">
          <PrivacyTab {...model} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function ProfileTab({ me, consents, saveProfile }: AccountModel) {
  const personalization = isGranted(consents.data, personalizationPurpose)
  const motion = useMotion()
  const [pending, setPending] = useState(false)
  const [saved, setSaved] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)
  const form = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: profileDefaults(me),
    values: profileDefaults(me),
  })
  const errors = form.formState.errors
  const visitorType = useWatch({ control: form.control, name: "visitor_type" })
  const visitReason = useWatch({ control: form.control, name: "visit_reason" })

  async function submit(values: ProfileValues) {
    setPending(true)
    setSaved(false)
    setFormError(null)
    setRequestId(null)
    try {
      const failure = await saveProfile(values)
      if (!failure) {
        setSaved(true)
        return
      }
      showFailure(failure)
    } finally {
      setPending(false)
    }
  }

  function showFailure(failure: SubmitFailure) {
    let known = false
    for (const [field, message] of Object.entries(failure.fieldErrors)) {
      const name = profileFields.find((item) => item === field)
      if (name) {
        form.setError(name, { message })
        known = true
      }
    }
    setRequestId(failure.requestId)
    if (!known) {
      setFormError(failure.message)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <form
        aria-labelledby="page-title"
        className="flex flex-col gap-6"
        noValidate
        onSubmit={(event) => {
          void form.handleSubmit(submit)(event)
        }}
      >
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="account-email">
              {pt.account.profile.email}
            </FieldLabel>
            <Input
              id="account-email"
              type="email"
              value={me.email}
              readOnly
              aria-describedby="account-email-note"
              className="h-11 md:h-8"
            />
            <FieldDescription id="account-email-note">
              {pt.account.profile.emailNote}
            </FieldDescription>
          </Field>
          <Field data-invalid={errors.full_name ? true : undefined}>
            <FieldLabel htmlFor="account-full-name">
              {pt.account.profile.fullName}
            </FieldLabel>
            <Input
              id="account-full-name"
              autoComplete="name"
              disabled={pending}
              aria-invalid={errors.full_name ? true : undefined}
              aria-describedby={
                errors.full_name ? "account-full-name-error" : undefined
              }
              className="h-11 md:h-8"
              {...form.register("full_name")}
            />
            {errors.full_name ? (
              <FieldError id="account-full-name-error">
                {errors.full_name.message}
              </FieldError>
            ) : null}
          </Field>
          <Field data-invalid={errors.phone ? true : undefined}>
            <FieldLabel htmlFor="account-phone">
              {pt.account.profile.phone}
            </FieldLabel>
            <Input
              id="account-phone"
              type="tel"
              autoComplete="tel"
              disabled={pending}
              aria-invalid={errors.phone ? true : undefined}
              aria-describedby={errors.phone ? "account-phone-error" : undefined}
              className="h-11 md:h-8"
              {...form.register("phone")}
            />
            <FieldDescription>{pt.account.profile.phoneHint}</FieldDescription>
            {errors.phone ? (
              <FieldError id="account-phone-error">
                {errors.phone.message}
              </FieldError>
            ) : null}
          </Field>
          {personalization ? (
            <>
              <ChoiceField
                label={pt.account.profile.visitorType}
                value={visitorType}
                options={visitorTypes}
                labels={pt.registration.visitorTypes}
                error={errors.visitor_type?.message}
                onChange={(value) =>
                  form.setValue("visitor_type", value, { shouldDirty: true })
                }
              />
              <ChoiceField
                label={pt.account.profile.visitReason}
                value={visitReason}
                options={visitReasons}
                labels={pt.registration.visitReasons}
                error={errors.visit_reason?.message}
                onChange={(value) =>
                  form.setValue("visit_reason", value, { shouldDirty: true })
                }
              />
            </>
          ) : (
            <p className="text-body text-foreground">
              {pt.account.profile.sensitiveOff}
            </p>
          )}
        </FieldGroup>
        {formError ? (
          <p role="alert" className="text-body text-danger">
            {formError}
          </p>
        ) : null}
        {requestId ? <RequestIdCopy requestId={requestId} /> : null}
        {saved ? (
          <p role="status" className="text-body text-foreground">
            {pt.account.profile.saved}
          </p>
        ) : null}
        <Button
          type="submit"
          className="min-h-11 w-fit md:min-h-8"
          disabled={pending}
        >
          {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
          {pending ? pt.account.profile.saving : pt.account.profile.save}
        </Button>
      </form>
      <FieldSet>
        <FieldLegend>{pt.account.profile.motionTitle}</FieldLegend>
        <FieldDescription>{pt.account.profile.motionHint}</FieldDescription>
        <ToggleGroup
          type="single"
          value={motion.preference}
          aria-label={pt.account.profile.motionTitle}
          onValueChange={(value) => {
            if (value) {
              motion.setPreference(value as MotionPreference)
            }
          }}
        >
          {motionOptions.map((option) => (
            <ToggleGroupItem key={option.value} value={option.value}>
              {option.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </FieldSet>
    </div>
  )
}

function ChoiceField<T extends string>({
  label,
  value,
  options,
  labels,
  error,
  onChange,
}: {
  label: string
  value: string
  options: readonly T[]
  labels: Record<T, string>
  error?: string
  onChange: (value: string) => void
}) {
  return (
    <Field data-invalid={error ? true : undefined}>
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
      {error ? <FieldError>{error}</FieldError> : null}
    </Field>
  )
}

function ConversationsTab({ conversations }: AccountModel) {
  if (conversations.isPending) {
    return (
      <div
        className="flex flex-col gap-3"
        role="status"
        aria-label={pt.account.conversations.loading}
      >
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-2/3" />
      </div>
    )
  }
  if (conversations.isError) {
    return (
      <p role="alert" className="text-body text-danger">
        {pt.account.loadError}
      </p>
    )
  }
  if (conversations.data.length === 0) {
    return (
      <p className="text-body text-foreground">
        {pt.account.conversations.empty}
      </p>
    )
  }
  return (
    <ul
      aria-label={pt.account.conversations.listLabel}
      className="flex flex-col gap-2"
    >
      {conversations.data.map((conversation) => (
        <li key={conversation.id}>
          <Link
            to={`/ask/${conversation.id}`}
            className="flex min-h-11 flex-col gap-1 rounded-xl bg-card p-3 text-body text-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <span className="truncate">
              {conversation.first_question ?? pt.account.conversations.untitled}
            </span>
            <span className="text-label text-muted-foreground">
              {formatDate(conversation.created_at)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function PrivacyTab({
  consents,
  changingPurpose,
  setConsent,
  exportData,
  deleteAccount,
}: AccountModel) {
  const [consentFailure, setConsentFailure] = useState<SubmitFailure | null>(
    null,
  )
  const [exporting, setExporting] = useState(false)
  const [exportMessage, setExportMessage] = useState<SubmitFailure | "done" | null>(null)

  async function toggle(purpose: OptionalPurpose, granted: boolean) {
    setConsentFailure(null)
    setConsentFailure(await setConsent(purpose, granted))
  }

  async function runExport() {
    setExporting(true)
    setExportMessage(null)
    try {
      setExportMessage((await exportData()) ?? "done")
    } finally {
      setExporting(false)
    }
  }

  if (consents.isPending) {
    return (
      <div
        className="flex flex-col gap-3"
        role="status"
        aria-label={pt.loading}
      >
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }
  if (consents.isError) {
    return (
      <p role="alert" className="text-body text-danger">
        {pt.account.loadError}
      </p>
    )
  }

  const terms = consentFor(consents.data, termsPurpose)
  return (
    <div className="flex flex-col gap-8">
      <FieldSet>
        <FieldLegend>{pt.account.privacy.consentsTitle}</FieldLegend>
        <FieldDescription>{pt.account.privacy.consentsLead}</FieldDescription>
        <FieldGroup>
          <Field>
            <FieldContent>
              <p className="text-label text-foreground">
                {pt.account.privacy.termsRequired}
              </p>
              <FieldDescription>
                {pt.account.privacy.termsRequiredNote}{" "}
                {terms?.document_version
                  ? pt.account.privacy.version.replace(
                      "{version}",
                      terms.document_version,
                    )
                  : null}
              </FieldDescription>
            </FieldContent>
          </Field>
          <ConsentSwitch
            id="consent-personalization"
            label={pt.account.privacy.personalization}
            note={pt.account.privacy.personalizationNote}
            checked={isGranted(consents.data, personalizationPurpose)}
            grantedAt={consentFor(consents.data, personalizationPurpose)?.granted_at}
            pending={changingPurpose === personalizationPurpose}
            onChange={(checked) => toggle(personalizationPurpose, checked)}
          />
          <ConsentSwitch
            id="consent-quality"
            label={pt.account.privacy.quality}
            note={pt.account.privacy.qualityNote}
            checked={isGranted(consents.data, qualityPurpose)}
            grantedAt={consentFor(consents.data, qualityPurpose)?.granted_at}
            pending={changingPurpose === qualityPurpose}
            onChange={(checked) => toggle(qualityPurpose, checked)}
          />
        </FieldGroup>
        {consentFailure ? (
          <div className="flex flex-col gap-2">
            <p role="alert" className="text-body text-danger">
              {pt.account.privacy.changeFailed}
            </p>
            {consentFailure.requestId ? (
              <RequestIdCopy requestId={consentFailure.requestId} />
            ) : null}
          </div>
        ) : null}
      </FieldSet>

      <section className="flex flex-col gap-3" aria-labelledby="export-title">
        <h2 id="export-title" className="text-label text-foreground-strong">
          {pt.account.privacy.exportTitle}
        </h2>
        <p className="text-body text-foreground">
          {pt.account.privacy.exportLead}
        </p>
        <Button
          type="button"
          variant="outline"
          className="min-h-11 w-fit md:min-h-8"
          disabled={exporting}
          onClick={() => {
            void runExport()
          }}
        >
          {exporting ? <Spinner aria-hidden data-icon="inline-start" /> : null}
          {exporting
            ? pt.account.privacy.exporting
            : pt.account.privacy.exportButton}
        </Button>
        {exportMessage === "done" ? (
          <p role="status" className="text-body text-foreground">
            {pt.account.privacy.exported}
          </p>
        ) : null}
        {exportMessage && exportMessage !== "done" ? (
          <div className="flex flex-col gap-2">
            <p role="alert" className="text-body text-danger">
              {exportMessage.message}
            </p>
            {exportMessage.requestId ? (
              <RequestIdCopy requestId={exportMessage.requestId} />
            ) : null}
          </div>
        ) : null}
      </section>

      <DeleteSection deleteAccount={deleteAccount} />

      <Button asChild variant="link" className="h-11 w-fit px-0 md:h-8">
        <Link to="/privacy#pedidos">{pt.account.privacy.requestsLink}</Link>
      </Button>
    </div>
  )
}

function ConsentSwitch({
  id,
  label,
  note,
  checked,
  grantedAt,
  pending,
  onChange,
}: {
  id: string
  label: string
  note: string
  checked: boolean
  grantedAt: string | null | undefined
  pending: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <Field orientation="horizontal" data-disabled={pending || undefined}>
      <Switch
        id={id}
        checked={checked}
        disabled={pending}
        aria-describedby={`${id}-note`}
        onCheckedChange={onChange}
      />
      <FieldContent>
        <FieldLabel htmlFor={id}>{label}</FieldLabel>
        <FieldDescription id={`${id}-note`}>
          {note} {checked ? grantedOn(grantedAt) : pt.account.privacy.off}
        </FieldDescription>
      </FieldContent>
    </Field>
  )
}

function DeleteSection({
  deleteAccount,
}: {
  deleteAccount: AccountModel["deleteAccount"]
}) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState("")
  const [pending, setPending] = useState(false)
  const [failure, setFailure] = useState<SubmitFailure | null>(null)

  async function confirm() {
    setPending(true)
    setFailure(null)
    try {
      setFailure(await deleteAccount())
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="flex flex-col gap-3" aria-labelledby="delete-title">
      <h2 id="delete-title" className="text-label text-foreground-strong">
        {pt.account.privacy.deleteTitle}
      </h2>
      <p className="text-body text-foreground">
        {pt.account.privacy.deleteLead}
      </p>
      <AlertDialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next)
          if (!next) {
            setText("")
            setFailure(null)
          }
        }}
      >
        <AlertDialogTrigger asChild>
          <Button
            type="button"
            variant="destructive"
            className="min-h-11 w-fit md:min-h-8"
          >
            {pt.account.privacy.deleteButton}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pt.account.privacy.deleteDialogTitle}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pt.account.privacy.deleteDialogBody}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Field data-invalid={failure ? true : undefined}>
            <FieldLabel htmlFor="delete-confirmation">
              {pt.account.privacy.deleteConfirmLabel}
            </FieldLabel>
            <Input
              id="delete-confirmation"
              autoComplete="off"
              value={text}
              disabled={pending}
              aria-invalid={failure ? true : undefined}
              className="h-11 md:h-8"
              onChange={(event) => setText(event.target.value)}
            />
          </Field>
          {failure ? (
            <div className="flex flex-col gap-2">
              <p role="alert" className="text-body text-danger">
                {failure.message}
              </p>
              {failure.requestId ? (
                <RequestIdCopy requestId={failure.requestId} />
              ) : null}
            </div>
          ) : null}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending}>
              {pt.account.privacy.deleteCancel}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={pending || !deleteConfirmed(text)}
              onClick={(event) => {
                event.preventDefault()
                void confirm()
              }}
            >
              {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
              {pending
                ? pt.account.privacy.deleting
                : pt.account.privacy.deleteConfirm}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
