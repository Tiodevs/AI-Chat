/**
 * Aviso de Privacidade e canal do titular, em `/privacy`.
 *
 * Camada: view (SDD 13.2). Recebe a versão e o contato do encarregado de
 * `useLegalVersions` e o e-mail e o `submit` de `usePrivacyRequest`, pela
 * rota `app/routes/privacy.tsx`, e não chama a API. O texto do Aviso mora
 * em `pt.privacyNotice` (`i18n/pt.ts`); as âncoras e as regras do
 * formulário, em `model.ts`. O formulário usa React Hook Form com Zod.
 *
 * SDD 15.5 (Privacidade), 11.5 (canal do titular), 11.7 (operadores com
 * país e finalidade), 11.9 (os dois cookies) e 11.11.
 */
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

// Atalho para os textos de cada seção do Aviso.
const notice = pt.privacyNotice.sections

/**
 * O Aviso em seções curtas com âncoras, um sumário de links no topo e o
 * formulário do canal na última seção (SDD 15.5).
 *
 * Efeito colateral: quando a URL chega com uma âncora, como a da seção
 * `pedidos` no link da conta, a tela rola até a seção. O roteador troca a
 * página sem recarregar, então o navegador não faz essa rolagem sozinho.
 */
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

  // Rola até a seção da âncora sempre que o `hash` da URL muda. O
  // `slice(1)` tira o primeiro caractere do `hash` e deixa só o `id`.
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
        <p className="text-body text-foreground">
          {pt.privacyNotice.fictional}
        </p>
      </div>

      {/* Sumário da página ("Nesta página"). São âncoras comuns, e o
          navegador rola até a seção sem passar pelo roteador. */}
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

      {/* O contato do encarregado vem de `PRIVACY_CONTACT_EMAIL` na API
          (SDD 12). Sem ele, o texto manda para o canal no fim da página. */}
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

      <NoticeSection id="whatsapp" title={notice.whatsapp.title}>
        <Paragraphs items={notice.whatsapp.body} />
      </NoticeSection>

      {/* Os operadores, com país e finalidade (SDD 11.7 e 30.9.1). */}
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

      {/* Os dois cookies estritamente necessários e a preferência de
          movimento no `localStorage`. Sem cookie de análise, não há banner
          de consentimento (SDD 11.9). */}
      <NoticeSection id="cookies" title={notice.cookies.title}>
        <p className="text-body text-foreground">{notice.cookies.lead}</p>
        <NoticeTable
          columns={notice.cookies.columns}
          rows={notice.cookies.rows}
        />
        <p className="text-body text-foreground">{notice.cookies.storage}</p>
      </NoticeSection>

      <NoticeSection id="seguranca" title={notice.security.title}>
        <Paragraphs items={notice.security.body} />
      </NoticeSection>

      <NoticeSection id="incidentes" title={notice.incidents.title}>
        <Paragraphs items={notice.incidents.body} />
      </NoticeSection>

      {/* O canal do titular. A âncora `pedidos` é a do link da conta, e o
          título `pedidos-title` também dá nome ao formulário. */}
      <NoticeSection id="pedidos" title={notice.channel.title}>
        <p className="text-body text-foreground">{notice.channel.lead}</p>
        <RequestForm email={email} submit={submit} />
      </NoticeSection>
    </div>
  )
}

/**
 * Uma seção do Aviso. O `<section>` recebe o `id` da âncora e o nome do
 * próprio título (`aria-labelledby`), o que o torna uma região que o leitor
 * de tela lista. `scroll-mt-6` deixa uma folga acima do título quando a
 * âncora rola até ela.
 */
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

/** Parágrafos de texto. O texto serve de `key`: eles não se repetem. */
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

/**
 * Tabela do Aviso. A primeira célula de cada linha é cabeçalho de linha
 * (`th` com `scope="row"`): o leitor de tela anuncia o dado, o operador ou
 * o cookie junto de cada valor. Uma tabela larga rola na horizontal dentro
 * do contorno, sem empurrar a página.
 */
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
                )
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Os campos que podem receber um erro do servidor. Um `field_errors` com
// outro nome vira o erro geral do formulário.
const requestFields = ["contact_email", "request_type", "description"] as const

/**
 * Formulário do canal do titular (SDD 11.5 e 15.5). Valida com o Zod antes
 * do envio. No sucesso, mostra o prazo de resposta com `role="status"` e
 * recomeça vazio, mantendo o e-mail de quem está na conta.
 *
 * Um erro de campo do servidor vai para o campo. Os demais, como o limite
 * diário do canal, aparecem com `role="alert"` e o `request_id`.
 */
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
  // O `zodResolver` valida com o `requestSchema` no envio. A opção `values`
  // segue o `email`: quando o perfil termina de carregar depois da tela, o
  // formulário recomeça com o e-mail do membro. Se a pessoa já tinha
  // começado a digitar, esse recomeço apaga o que ela escreveu.
  const form = useForm<RequestValues>({
    resolver: zodResolver(requestSchema),
    defaultValues: emptyRequest(email),
    values: emptyRequest(email),
  })
  const errors = form.formState.errors
  // O tipo é um `ToggleGroup`, sem `register`: o `useWatch` lê o valor para
  // marcar a opção escolhida.
  const requestType = useWatch({ control: form.control, name: "request_type" })

  /**
   * Envia o pedido pelo `submit` do hook.
   *
   * 1. Limpa a confirmação, o erro e o `request_id` anteriores.
   * 2. No sucesso, mostra o prazo e recomeça o formulário.
   * 3. Na falha, põe cada erro de campo conhecido no campo dele. Sem nenhum,
   *    a mensagem geral aparece acima do botão.
   */
  async function send(values: RequestValues) {
    // 1.
    setPending(true)
    setSent(null)
    setFormError(null)
    setRequestId(null)
    try {
      const result = await submit(values)
      // 2.
      if (result.ok) {
        setSent(sentMessage(result.dueAt))
        form.reset(emptyRequest(email))
        return
      }
      // 3.
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
            // Antes do primeiro envio, escolher um tipo não valida, para o
            // erro não aparecer cedo. Depois dele, cada escolha revalida e o
            // erro some na hora.
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
        {/* A dica fica sempre ligada ao campo e pede para não incluir dados
            de saúde (SDD 11.4). O erro entra junto quando existe. */}
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
