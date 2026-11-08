/**
 * Tela `/register`: criar a conta conversando, sem perder o controle dos
 * dados. Seção 15.5 do SDD (Cadastro por conversa) e padrões da seção 15.6.
 *
 * View: recebe o retorno de `useRegistrationChat`, por
 * `app/routes/register.tsx`, e não chama a API. Mostra a transcrição, o
 * aviso de falha, o cartão do que a IA entendeu e, no rodapé, o passo
 * atual: resposta livre, senha, revisão ou aceite, conforme o `next_step`
 * (seção 7.2). Usa `AssistantBubble`, `UserMessage`, `ChatErrorNotice`,
 * `ProfileSummaryCard`, `PasswordCard` e `ConsentFieldSet`, de
 * `components/patterns`.
 */
import { PanelRightClose, PanelRightOpen, SendHorizontal } from "lucide-react"
import { useEffect, useId, useRef, useState, type MouseEvent } from "react"
import { Link, useNavigate } from "react-router"

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

/** Tudo o que `useRegistrationChat` devolve. A tela recebe o objeto todo. */
type Chat = ReturnType<typeof useRegistrationChat>

/**
 * Página do cadastro por conversa.
 *
 * O botão Ver o que entendemos abre o `ProfileSummaryCard`, que começa
 * oculto: à direita do chat no desktop, de 1024 px para cima, e acima dele
 * nas telas menores. O link Usar o formulário leva a sessão para o
 * formulário e espera a mensagem a caminho antes de sair (J4). O texto do
 * campo só é limpo quando a API aceita o turno.
 */
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
  // O `MotionProvider` acompanha `(min-width: 1024px)` e decide onde o
  // cartão de resumo fica.
  const { isDesktop } = useMotion()
  const navigate = useNavigate()
  const [draft, setDraft] = useState("")
  // Ir para o formulário com uma mensagem a caminho perderia o campo que ela traz (J4):
  // o clique espera só a mensagem em andamento e então abre o formulário com a sessão.
  // Outras ações, como a criação da conta, não seguram o link.
  const leavingForForm = useRef(false)
  useEffect(() => {
    if (leavingForForm.current && outgoing === null) {
      leavingForForm.current = false
      void navigate(formPath(session?.id ?? null))
    }
  }, [outgoing, navigate, session?.id])

  /**
   * Clique em Usar o formulário. Com uma mensagem a caminho, segura o link,
   * e o efeito acima navega quando `outgoing` volta a `null`.
   */
  function openForm(event: MouseEvent<HTMLAnchorElement>) {
    if (outgoing !== null) {
      event.preventDefault()
      leavingForForm.current = true
    }
  }
  // Padrão de disclosure: o botão diz com `aria-expanded` se o cartão está
  // aberto e aponta para ele com `aria-controls`.
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

  /**
   * Envia o rascunho e só limpa o campo se a API aceitou o turno. Numa
   * falha, o texto fica no compositor (seção 15.5, Estados).
   */
  async function sendDraft(text: string) {
    const sent = await send(text)
    if (sent) {
      setDraft("")
    }
  }

  // Texto do turno que falhou, para o Tentar de novo do aviso.
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
          <Link to={formPath(session?.id ?? null)} onClick={openForm}>
            {pt.registration.useForm}
          </Link>
        </Button>
      </div>
      <div className="flex flex-1 flex-col gap-4 lg:flex-row lg:items-start">
        {/* Abaixo de 1024 px, o cartão fica acima do chat. */}
        {summaryOpen && !isDesktop ? <div id={summaryId}>{summary}</div> : null}
        <section
          aria-label={pt.registration.thread}
          className="flex min-w-0 flex-1 flex-col rounded-2xl border border-border bg-shell"
        >
          <div className="flex flex-1 flex-col gap-4 p-4 md:p-5">
            {/* Enquanto a sessão abre, o assistente aparece escrevendo. */}
            {loading ? <AssistantBubble typing /> : null}
            {/* Só o envio de um turno mostra o assistente escrevendo. A
                edição do cartão, a senha e a revisão não têm `outgoing`. */}
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
                // Sem sessão, o aviso é o único conteúdo e não fecha.
                onDismiss={session ? dismissNotice : undefined}
                onRetry={
                  retryText && !pending
                    ? () => {
                        void sendDraft(retryText)
                      }
                    : undefined
                }
              >
                {/* Com o modelo fora (503) ou sem sessão, o aviso oferece
                    o formulário (seção 7.2), que leva os campos entendidos. */}
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
          {/* Rodapé fixo do painel, com o passo atual (seção 15.5). */}
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
        {/* No desktop, o cartão fica à direita e acompanha a rolagem. */}
        {summaryOpen && isDesktop ? (
          <div id={summaryId} className="sticky top-0 w-80 shrink-0">
            {summary}
          </div>
        ) : null}
      </div>
    </div>
  )
}

/**
 * Campos vazios, para a contagem do botão antes de a sessão abrir. Igual a
 * `emptyFields`, do `model.ts`.
 */
function emptySummaryFields() {
  return {
    full_name: null,
    email: null,
    phone: null,
    visitor_type: null,
    visit_reason: null,
  }
}

/**
 * Transcrição do chat, a mensagem a caminho e o assistente escrevendo.
 *
 * A região ao vivo, escondida, lê a última fala do assistente, ou avisa que
 * ele está escrevendo. Cada mudança no número de falas ou em `typing` rola
 * a lista até o fim. As falas não têm id, então a chave junta a data e a
 * posição. Com o e-mail já cadastrado, o botão Entrar aparece logo abaixo
 * da resposta (seção 15.5, Estados).
 */
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

  // O `?.` depois de `scrollIntoView` cobre o jsdom dos testes, que não tem
  // o método. A rolagem é suave mesmo com movimento reduzido.
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
        {/* `ps-10` alinha o botão ao balão, depois do avatar de 32 px e do
            espaço de 8 px. */}
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

/**
 * Escolhe o rodapé pelo `next_step` da sessão. A senha, a revisão e o
 * aceite têm controles próprios: a interface de senha aparece porque a
 * resposta diz `next_step = password` (seção 7.2). Os passos de campo usam
 * a resposta livre, com Pular nos opcionais.
 */
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

/**
 * Compositor do chat do cadastro, com Enviar dentro do campo (seção 15.5).
 *
 * O campo cresce com o texto. Enter envia e Shift+Enter quebra a linha
 * (seção 15.8). Nos passos opcionais, a dica e o botão Pular aparecem
 * abaixo, e a dica descreve o campo. Enquanto o turno vai, o campo e os
 * botões ficam desabilitados.
 */
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

  // Zera a altura e mede o conteúdo a cada mudança: o campo cresce com o
  // texto até o `max-h-40` do CSS e depois rola.
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
            // O mesmo teto da API para uma mensagem (`MAX_MESSAGE_CHARS`).
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

/**
 * Passo da senha: o `PasswordCard` no lugar do compositor (seção 15.5). Com
 * `moveFocus`, o foco vai para o campo quando a entrada M12 termina (seção
 * 16.3), com ou sem movimento reduzido. A senha fica só no estado deste
 * componente até o envio.
 */
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

/**
 * Passo da revisão: Está certo e Quero corrigir. O resumo vem do próprio
 * assistente, na conversa, e o cartão lateral não abre sozinho (seção
 * 15.5, Passo de revisão).
 */
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

/**
 * Passo do aceite: o `ConsentFieldSet` e o botão Criar conta (seção 15.5,
 * Passo de aceite).
 *
 * Os aceites começam desmarcados. Os erros dos obrigatórios só aparecem
 * depois da primeira tentativa de envio, e o erro do servidor vence o
 * local. Só `accept_terms` e `age_18_plus` chegam ao `ConsentFieldSet`.
 */
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

/** Lugar do cartão de resumo enquanto a sessão não abriu. */
function SummarySkeleton() {
  return <Skeleton className="h-40 w-full" />
}
