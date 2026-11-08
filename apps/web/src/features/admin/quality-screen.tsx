/**
 * Qualidade do admin, em `/admin/quality`: filtros, os desfechos e o
 * feedback do período, a lista de conversas pseudonimizadas e o inspetor de
 * uma conversa, com o link para o rastro no LangSmith.
 *
 * Camada: view (SDD 13.2). Recebe o `QualityModel` de `useQuality` pela
 * rota `app/routes/admin-quality.tsx` e não chama a API. Usa as regras de
 * `insights-model.ts`, o `formatDateTime` de `documents-model.ts`, o
 * `DataTable`, o `PseudonymBadge`, o `SegmentedStatusCard` e o
 * `RequestIdCopy` de `components/patterns` e o `Sheet` e o `Select` de
 * `components/ui`.
 *
 * Privacidade: a tela só mostra pseudônimos. A identidade de um membro só
 * aparece pela ação Revelar identidade, com motivo e auditoria (SDD 11.8).
 * SDD 15.5 (Qualidade), 18.4 e 18.5 (rastro no LangSmith) e Jornada J7.
 */
import { ExternalLink } from "lucide-react"
import { useState, type FormEvent } from "react"

import { PageHeading } from "@/app/page-heading.tsx"
import { DataTable, type DataTableColumn } from "@/components/patterns/data-table.tsx"
import { PseudonymBadge } from "@/components/patterns/pseudonym-badge.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { SegmentedStatusCard } from "@/components/patterns/segmented-status-card.tsx"
import { Badge } from "@/components/ui/badge.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field.tsx"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select.tsx"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { Textarea } from "@/components/ui/textarea.tsx"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group.tsx"
import { pt } from "@/i18n/pt.ts"

import { formatDateTime } from "./documents-model.ts"
import {
  feedbackOrder,
  feedbackTone,
  outcomeLabel,
  outcomeOrder,
  outcomeTone,
  periods,
  reasonIsValid,
  segmentsFrom,
  subjectLabel,
  type ConversationSummary,
  type Inspection,
  type InspectorMessage,
  type Tone,
} from "./insights-model.ts"
import type { QualityModel, RevealResult } from "./useInsights.ts"

const q = pt.quality
const t = pt.insights
// O valor de "todos" nos filtros. O `Select` do Radix não aceita item com
// valor vazio, então `all` representa a falta de filtro e vira `null` no
// estado.
const anyValue = "all"

// Traduz o tom do modelo para a variante do `Badge`. Neutro vira
// `secondary`, a superfície sem cor.
const badgeTone: Record<Tone, "success" | "warning" | "danger" | "info" | "secondary"> = {
  success: "success",
  warning: "warning",
  danger: "danger",
  info: "info",
  neutral: "secondary",
}

/** Badge do desfecho, com nome e cor. Sem desfecho, o texto "Sem dados". */
function OutcomeTag({ outcome }: { outcome: string | null }) {
  if (!outcome) {
    return <span className="text-muted-foreground">{t.notAvailable}</span>
  }
  const tone = (outcomeTone as Record<string, Tone>)[outcome] ?? "neutral"
  return <Badge variant={badgeTone[tone]}>{outcomeLabel(outcome)}</Badge>
}

/**
 * Página da qualidade (SDD 15.5). Da lista ao rastro do LangSmith são dois
 * cliques: Abrir conversa e o link do rastro no inspetor (Jornada J7).
 */
export function QualityScreen(model: QualityModel) {
  const data = model.quality
  // O resumo da linha aberta dá o pseudônimo ao título do `Sheet` antes de
  // a conversa chegar.
  const selected = data?.conversations.find((item) => item.id === model.openId) ?? null

  // Colunas: pessoa (o cabeçalho da linha), última atividade, perguntas,
  // último desfecho, feedback e a ação de abrir.
  const columns: DataTableColumn<ConversationSummary>[] = [
    {
      key: "subject",
      header: q.table.subject,
      rowHeader: true,
      cell: (row) => (
        <PseudonymBadge
          kind={row.subject_kind}
          pseudonym={row.pseudonym}
          kindLabel={q.subject[row.subject_kind]}
        />
      ),
    },
    { key: "activity", header: q.table.lastActivity, cell: (row) => formatDateTime(row.last_activity_at) },
    { key: "questions", header: q.table.questions, cell: (row) => row.questions },
    { key: "outcome", header: q.table.lastOutcome, cell: (row) => <OutcomeTag outcome={row.last_outcome} /> },
    {
      key: "feedback",
      header: q.table.feedback,
      cell: (row) =>
        row.helpful + row.not_helpful === 0
          ? q.table.noFeedback
          : q.table.feedbackCounts
              .replace("{helpful}", String(row.helpful))
              .replace("{notHelpful}", String(row.not_helpful)),
    },
    {
      key: "actions",
      header: q.table.actions,
      cell: (row) => (
        // O nome acessível começa pelo texto visível e diz de quem é a
        // conversa, para distinguir as linhas (SDD 15.8).
        <Button
          size="sm"
          variant="outline"
          aria-label={`${q.table.open}: ${subjectLabel(row.subject_kind, row.pseudonym)}`}
          onClick={() => {
            model.open(row.id)
          }}
        >
          {q.table.open}
        </Button>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <PageHeading title={pt.pages.quality} />
        <p className="text-body text-muted-foreground">{q.lead}</p>
      </header>

      <Filters model={model} />

      {model.loadError ? (
        <p role="alert" className="text-body text-destructive">
          {t.loadFailed}
        </p>
      ) : null}

      {/* Desfechos e feedback do período, de todas as conversas, inclusive
          as que não entram na lista por falta de consentimento (SDD 12). */}
      {data ? (
        <SegmentedStatusCard
          title={t.outcomesCard.title}
          emptyText={t.outcomesCard.empty}
          views={[
            {
              key: "outcome",
              label: t.outcomesCard.outcome,
              segments: segmentsFrom(outcomeOrder, data.outcomes, t.outcomes, outcomeTone),
            },
            {
              key: "feedback",
              label: t.outcomesCard.feedback,
              segments: segmentsFrom(feedbackOrder, data.feedback, t.feedback, feedbackTone),
            },
          ]}
        />
      ) : (
        <Skeleton className="h-40 w-full" />
      )}

      <DataTable
        caption={q.table.caption}
        columns={columns}
        rows={data?.conversations}
        rowKey={(row) => row.id}
        loading={model.loading}
        empty={q.table.empty}
      />

      <InspectorSheet
        open={model.openId !== null}
        summary={selected}
        inspection={model.inspection}
        loading={model.inspectionLoading}
        failed={model.inspectionError}
        onClose={() => {
          model.open(null)
        }}
        reveal={model.reveal}
      />
    </div>
  )
}

/**
 * Filtros de período, desfecho e feedback (SDD 15.5). Cada mudança troca os
 * filtros do modelo, e a lista é relida com a chave nova.
 */
function Filters({ model }: { model: QualityModel }) {
  const { filters, setFilters } = model
  return (
    <section aria-label={q.filters.title} className="flex flex-wrap items-end gap-4">
      {/* O `ToggleGroup` não é um campo nativo: o rótulo é um `span` ligado
          por `aria-labelledby`. Clicar no período já marcado manda `""`, e
          o clique é ignorado. */}
      <div className="flex flex-col gap-2">
        <span className="text-label text-muted-foreground" id="quality-period">
          {t.period.label}
        </span>
        <ToggleGroup
          type="single"
          value={String(filters.period)}
          aria-labelledby="quality-period"
          onValueChange={(value) => {
            if (value) {
              setFilters({ ...filters, period: Number(value) === 30 ? 30 : 7 })
            }
          }}
        >
          {periods.map((value) => (
            <ToggleGroupItem key={value} value={String(value)}>
              {value === 7 ? t.period.days7 : t.period.days30}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <div className="flex flex-col gap-2">
        <label className="text-label text-muted-foreground" htmlFor="quality-outcome">
          {q.filters.outcome}
        </label>
        <Select
          value={filters.outcome ?? anyValue}
          onValueChange={(value) => {
            setFilters({ ...filters, outcome: value === anyValue ? null : value })
          }}
        >
          <SelectTrigger id="quality-outcome" className="min-w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={anyValue}>{q.filters.anyOutcome}</SelectItem>
            {outcomeOrder.map((outcome) => (
              <SelectItem key={outcome} value={outcome}>
                {t.outcomes[outcome]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-label text-muted-foreground" id="quality-feedback">
          {q.filters.feedback}
        </span>
        <ToggleGroup
          type="single"
          value={filters.feedback ?? anyValue}
          aria-labelledby="quality-feedback"
          onValueChange={(value) => {
            if (value) {
              setFilters({ ...filters, feedback: value === anyValue ? null : value })
            }
          }}
        >
          <ToggleGroupItem value={anyValue}>{q.filters.anyFeedback}</ToggleGroupItem>
          {feedbackOrder.map((key) => (
            <ToggleGroupItem key={key} value={key}>
              {t.feedback[key]}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
    </section>
  )
}

/**
 * `Sheet` inspetor de uma conversa (SDD 15.5): as mensagens com o desfecho,
 * as fontes, a versão do prompt, a latência, o `request_id` e o rastro no
 * LangSmith. Numa conversa de membro, oferece Revelar identidade; numa de
 * convidado, avisa que não há identidade.
 *
 * O pseudônimo vem da conversa carregada ou, antes dela, do resumo da
 * linha, para o título não ficar vazio.
 */
function InspectorSheet({
  open,
  summary,
  inspection,
  loading,
  failed,
  onClose,
  reveal,
}: {
  open: boolean
  summary: ConversationSummary | null
  inspection: Inspection | undefined
  loading: boolean
  failed: boolean
  onClose: () => void
  reveal: QualityModel["reveal"]
}) {
  const kind = inspection?.subject_kind ?? summary?.subject_kind ?? "guest"
  const pseudonym = inspection?.pseudonym ?? summary?.pseudonym ?? ""
  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          onClose()
        }
      }}
    >
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{q.inspector.title.replace("{pseudonym}", pseudonym)}</SheetTitle>
          <SheetDescription>{q.inspector.description}</SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-4 px-4 pb-6">
          <PseudonymBadge kind={kind} pseudonym={pseudonym} kindLabel={q.subject[kind]} />
          {failed ? (
            <p role="alert" className="text-body text-destructive">
              {q.inspector.loadFailed}
            </p>
          ) : null}
          {loading && !inspection ? (
            <div className="flex flex-col gap-3" aria-busy="true" aria-label={q.inspector.loading}>
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : null}
          {inspection ? (
            <>
              {/* Só um membro tem identidade a revelar. A API responderia
                  409 numa conversa de convidado (SDD 12). */}
              {inspection.subject_kind === "member" ? (
                <RevealForm conversationId={inspection.id} reveal={reveal} />
              ) : (
                <p className="text-caption text-muted-foreground">{q.reveal.guestHint}</p>
              )}
              <ol className="flex flex-col gap-3">
                {inspection.messages.map((message) => (
                  <li key={message.id}>
                    <MessageItem message={message} />
                  </li>
                ))}
              </ol>
            </>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  )
}

/**
 * Uma mensagem no inspetor. A resposta do assistente mostra o desfecho, a
 * avaliação do visitante, as fontes e um rodapé com a versão do prompt, a
 * latência, o `request_id` e o rastro (SDD 15.5 e 18.5). Sem `trace_url`,
 * que depende de `LANGSMITH_RUN_URL_TEMPLATE` (SDD 18.4), aparece o id do
 * rastro no lugar do link.
 */
function MessageItem({ message }: { message: InspectorMessage }) {
  const assistant = message.role === "assistant"
  return (
    <article className="flex flex-col gap-2 rounded-lg bg-muted px-3 py-3">
      <header className="flex flex-wrap items-center gap-2 text-caption text-muted-foreground">
        <span className="font-medium text-foreground">
          {assistant ? q.inspector.assistant : q.inspector.user}
        </span>
        <span>{formatDateTime(message.created_at)}</span>
        {assistant ? <OutcomeTag outcome={message.outcome} /> : null}
        {message.rating != null ? (
          <Badge variant={message.rating > 0 ? "success" : "danger"}>
            {message.rating > 0 ? q.inspector.rating.helpful : q.inspector.rating.not_helpful}
          </Badge>
        ) : null}
      </header>
      <p className="text-body whitespace-pre-wrap text-foreground">{message.content}</p>
      {message.citations.length > 0 ? (
        <div className="flex flex-col gap-1">
          <span className="text-caption text-muted-foreground">{q.inspector.sources}</span>
          <ul className="flex flex-col gap-0.5 text-caption text-foreground">
            {message.citations.map((citation) => (
              <li key={`${String(citation.index)}-${citation.document_title}`}>
                [{citation.index}] {citation.document_title}
                {citation.heading ? ` · ${citation.heading}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {assistant ? (
        <footer className="flex flex-wrap items-center gap-3 text-caption text-muted-foreground">
          {message.prompt_version ? (
            <span>{q.inspector.promptVersion.replace("{version}", message.prompt_version)}</span>
          ) : null}
          {message.latency_ms != null ? (
            <span>{q.inspector.latency.replace("{ms}", String(message.latency_ms))}</span>
          ) : null}
          {message.request_id ? <RequestIdCopy requestId={message.request_id} /> : null}
          {/* O rastro abre em outra aba. `noreferrer noopener` não passa o
              endereço do Atrium nem o `window.opener` para o LangSmith. */}
          {message.trace_url ? (
            <a
              href={message.trace_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 text-foreground underline underline-offset-4"
            >
              {q.inspector.trace}
              <ExternalLink className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
            </a>
          ) : message.run_id ? (
            <span className="font-mono">{q.inspector.traceId.replace("{id}", message.run_id)}</span>
          ) : null}
        </footer>
      ) : null}
    </article>
  )
}

/**
 * Revelar identidade (SDD 11.8 e 15.5), em três estados: o botão, o
 * formulário com o motivo e o resultado com nome e e-mail.
 *
 * O motivo é conferido no navegador, de 10 a 500 caracteres, antes de
 * chamar a API, que grava `identity.reveal` com ele. A identidade revelada
 * fica só no estado deste componente: fechar o inspetor desmonta o
 * formulário, e ela some da tela.
 */
function RevealForm({
  conversationId,
  reveal,
}: {
  conversationId: string
  reveal: QualityModel["reveal"]
}) {
  // Os `useState` ficam antes dos retornos antecipados abaixo: o React
  // exige os mesmos hooks, na mesma ordem, em toda renderização.
  const [opened, setOpened] = useState(false)
  const [reason, setReason] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState<RevealResult | null>(null)

  // Revelada: o `role="status"` anuncia nome e e-mail ao leitor de tela.
  if (result?.ok) {
    return (
      <p role="status" className="rounded-lg bg-muted px-3 py-2 text-body text-foreground-strong">
        {q.reveal.revealed.replace("{name}", result.fullName).replace("{email}", result.email)}
      </p>
    )
  }

  if (!opened) {
    return (
      <Button
        variant="outline"
        className="w-fit"
        onClick={() => {
          setOpened(true)
        }}
      >
        {q.reveal.action}
      </Button>
    )
  }

  /**
   * Confere o motivo, chama a API e guarda o resultado. Na falha, um erro do
   * servidor no campo `reason` vence a mensagem geral.
   */
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!reasonIsValid(reason)) {
      setError(q.reveal.reasonInvalid)
      return
    }
    setPending(true)
    const outcome = await reveal(conversationId, reason)
    setPending(false)
    setResult(outcome)
    if (!outcome.ok) {
      setError(outcome.fieldErrors.reason ?? outcome.message)
    }
  }

  return (
    <form
      noValidate
      className="flex flex-col gap-3 rounded-lg bg-muted px-3 py-3"
      aria-labelledby="reveal-title"
      onSubmit={(event) => void submit(event)}
    >
      <h3 id="reveal-title" className="text-label text-foreground-strong">
        {q.reveal.title}
      </h3>
      <p className="text-caption text-muted-foreground">{q.reveal.description}</p>
      <Field data-invalid={error ? true : undefined}>
        <FieldLabel htmlFor="reveal-reason">{q.reveal.reason}</FieldLabel>
        {/* O `maxLength` conta o texto como digitado, e a API conta depois
            de juntar os espaços: o limite do campo é um pouco mais estrito
            que o do servidor. */}
        <Textarea
          id="reveal-reason"
          value={reason}
          maxLength={500}
          disabled={pending}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "reveal-reason-hint reveal-reason-error" : "reveal-reason-hint"}
          onChange={(event) => {
            setReason(event.target.value)
          }}
        />
        <FieldDescription id="reveal-reason-hint">{q.reveal.reasonHint}</FieldDescription>
        {error ? <FieldError id="reveal-reason-error">{error}</FieldError> : null}
      </Field>
      {result && !result.ok && result.requestId ? <RequestIdCopy requestId={result.requestId} /> : null}
      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
          {pending ? q.reveal.confirming : q.reveal.confirm}
        </Button>
        {/* Cancelar fecha o formulário e limpa o erro. O motivo digitado
            continua lá se o admin abrir o formulário de novo. */}
        <Button
          type="button"
          variant="ghost"
          disabled={pending}
          onClick={() => {
            setOpened(false)
            setError(null)
          }}
        >
          {q.reveal.cancel}
        </Button>
      </div>
    </form>
  )
}
