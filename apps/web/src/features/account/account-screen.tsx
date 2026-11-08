/**
 * Tela da conta do membro, em `/account`, com as abas Perfil, Conversas e
 * Privacidade.
 *
 * Camada: view (SDD 13.2). Recebe o `AccountModel` de `useAccount` pela
 * rota `app/routes/account.tsx` e não chama a API: cada ação é um callback
 * do modelo. Usa as regras de `model.ts`, o `useMotion` de
 * `motion/MotionProvider.tsx`, o `RequestIdCopy` e os componentes de
 * `components/ui`, com o formulário em React Hook Form e Zod.
 *
 * SDD 15.5 (Conta), 11.5 (direitos do titular), 8.5 (regras dos campos),
 * 15.8 (acessibilidade) e 16.4 (preferência de movimento).
 */
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

// Os campos do perfil que podem receber um erro do servidor. Um
// `field_errors` com outro nome vira o erro geral do formulário.
const profileFields = [
  "full_name",
  "phone",
  "visitor_type",
  "visit_reason",
] as const

// As três escolhas de movimento (SDD 16.4): seguir o sistema (`system`),
// reduzir sempre (`on`) ou animar sempre (`off`). O `MotionProvider` guarda
// a escolha no `localStorage`, que não sai do navegador (SDD 11.9).
const motionOptions: { value: MotionPreference; label: string }[] = [
  { value: "system", label: pt.profile.motionSystem },
  { value: "on", label: pt.profile.motionReduce },
  { value: "off", label: pt.profile.motionAllow },
]

/**
 * Página da conta: título e as três abas (SDD 15.5).
 *
 * As abas são do Radix e só a ativa fica montada. Trocar de aba desmonta a
 * anterior, então uma edição do perfil que não foi salva se perde. Os dados
 * do servidor ficam: moram no cache do TanStack Query, que o `useAccount`
 * lê.
 */
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

/**
 * Aba Perfil. Corrige nome e telefone e, com a personalização ativa, o tipo
 * de visitante e o motivo da visita. O e-mail é só leitura, porque é o
 * acesso da conta (SDD 15.5). A preferência de movimento também fica aqui,
 * mas não vai ao servidor.
 */
function ProfileTab({ me, consents, saveProfile }: AccountModel) {
  const personalization = isGranted(consents.data, personalizationPurpose)
  const motion = useMotion()
  const [pending, setPending] = useState(false)
  const [saved, setSaved] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)
  // O `zodResolver` valida com o `profileSchema` no envio. A opção `values`
  // segue o `me` do cache: quando o perfil muda, por exemplo depois de
  // salvar ou de revogar a personalização, o formulário recomeça dos dados
  // novos.
  const form = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: profileDefaults(me),
    values: profileDefaults(me),
  })
  const errors = form.formState.errors
  // Os dois campos são `ToggleGroup`, sem `register`. O `useWatch` lê o
  // valor do formulário para a tela marcar a opção escolhida.
  const visitorType = useWatch({ control: form.control, name: "visitor_type" })
  const visitReason = useWatch({ control: form.control, name: "visit_reason" })

  /** Salva o perfil e mostra a confirmação ou os erros devolvidos. */
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

  /**
   * Põe cada erro de campo do servidor no campo dele, com `setError`. Se
   * nenhum erro cai num campo da tela, a mensagem geral aparece acima do
   * botão. O `request_id` aparece nos dois casos.
   */
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
      {/* O formulário leva o nome do título da página (`page-title`, do
          `PageHeading`). `noValidate` desliga a validação do navegador:
          quem valida é o Zod, com as mensagens em português. */}
      <form
        aria-labelledby="page-title"
        className="flex flex-col gap-6"
        noValidate
        onSubmit={(event) => {
          void form.handleSubmit(submit)(event)
        }}
      >
        <FieldGroup>
          {/* O e-mail é o acesso da conta: só leitura, e `PATCH /v1/me` não
              o muda (SDD 12). */}
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
          {/* `aria-invalid` marca o campo com erro, e `aria-describedby` liga
              a mensagem ao campo para o leitor de tela (SDD 15.8). */}
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
          {/* Tipo de visitante e motivo da visita podem indicar que a pessoa
              é paciente, então só aparecem com a personalização ativa (SDD
              11.4 e 15.5). Sem ela, a nota diz onde ativar. */}
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
      {/* A preferência de movimento fica fora do `<form>`: vale na hora,
          sem salvar, e só neste navegador (SDD 16.4). */}
      <FieldSet>
        <FieldLegend>{pt.account.profile.motionTitle}</FieldLegend>
        <FieldDescription>{pt.account.profile.motionHint}</FieldDescription>
        <ToggleGroup
          type="single"
          value={motion.preference}
          aria-label={pt.account.profile.motionTitle}
          onValueChange={(value) => {
            // Clicar na opção já marcada faz o Radix mandar `""`. Aqui a
            // escolha não pode ficar vazia, então o clique é ignorado.
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

/**
 * Uma escolha numa lista fechada, como o tipo de visitante (SDD 8.5). O
 * `ToggleGroup` de escolha única do Radix expõe cada opção como `radio`
 * para o leitor de tela. Clicar de novo na opção marcada manda `""` e
 * desmarca: ao salvar, o campo vazio vira `null` e o servidor o limpa.
 */
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

/**
 * Aba Conversas: a lista com a primeira pergunta e a data de cada conversa,
 * cada item levando a `/ask/:id` (SDD 15.5). Tem os estados carregando,
 * erro, vazio ("Nenhuma conversa ainda.") e lista.
 */
function ConversationsTab({ conversations }: AccountModel) {
  // Enquanto carrega, o `role="status"` com nome diz ao leitor de tela o
  // que os skeletons representam.
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
            {/* `first_question` é nulo numa conversa sem pergunta gravada
                (SDD 12). */}
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

/**
 * Aba Privacidade (SDD 15.5 e 11.5): os interruptores dos consentimentos
 * opcionais com a data do aceite, a linha fixa dos Termos com a versão
 * aceita, a exportação dos dados, a exclusão da conta e o link para o canal
 * do titular.
 */
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
  // `"done"` mostra a confirmação, e um `SubmitFailure` mostra o erro.
  const [exportMessage, setExportMessage] = useState<SubmitFailure | "done" | null>(null)

  /** Muda um consentimento e guarda a falha, se houver, para o aviso. */
  async function toggle(purpose: OptionalPurpose, granted: boolean) {
    setConsentFailure(null)
    setConsentFailure(await setConsent(purpose, granted))
  }

  /** Baixa a exportação e mostra a confirmação ou o erro. */
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

  // Os Termos não têm interruptor: são obrigatórios para ter conta, e um novo
  // aceite só acontece pela tela `/legal/accept`. Aqui só aparece a versão.
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

      {/* Leva à seção `pedidos` do Aviso, o canal do titular, para o que a
          conta não resolve sozinha, como oposição (SDD 11.5). */}
      <Button asChild variant="link" className="h-11 w-fit px-0 md:h-8">
        <Link to="/privacy#pedidos">{pt.account.privacy.requestsLink}</Link>
      </Button>
    </div>
  )
}

/**
 * Interruptor de um consentimento opcional. O `checked` vem do cache dos
 * consentimentos, então ele só muda quando o servidor confirma; durante o
 * pedido, fica travado. A nota ao lado diz o que o consentimento cobre e a
 * data do aceite, como pede a seção 11.5 ("informação sobre não
 * consentir").
 */
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
        {/* No celular, o rótulo também é um alvo de toque de 44 px (SDD
            15.8): tocar nele liga ou desliga o interruptor. */}
        <FieldLabel htmlFor={id} className="max-md:min-h-11 max-md:items-center">
          {label}
        </FieldLabel>
        <FieldDescription id={`${id}-note`}>
          {note} {checked ? grantedOn(grantedAt) : pt.account.privacy.off}
        </FieldDescription>
      </FieldContent>
    </Field>
  )
}

/**
 * Excluir a conta, a última etapa da Jornada J5 (SDD 15.3 e 15.5). O
 * `AlertDialog` só libera o botão depois que a pessoa digita EXCLUIR, e
 * fechar o diálogo limpa o texto e a falha.
 */
function DeleteSection({
  deleteAccount,
}: {
  deleteAccount: AccountModel["deleteAccount"]
}) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState("")
  const [pending, setPending] = useState(false)
  const [failure, setFailure] = useState<SubmitFailure | null>(null)

  /**
   * Pede a exclusão. No sucesso, `deleteAccount` já navegou para o início.
   * Na falha, como o 403 de um admin (SDD 10.5), o erro fica no diálogo.
   */
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
                // O `AlertDialogAction` do Radix fecha o diálogo no clique. O
                // `preventDefault` o mantém aberto até a resposta, para uma
                // falha aparecer dentro dele.
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
