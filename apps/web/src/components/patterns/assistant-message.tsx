/**
 * Resposta do assistente na conversa (`/ask/:id?`): texto sem balão, à
 * esquerda, com chips de citação, lista de fontes e ações (seção 14.6).
 *
 * Renderiza cada estado da tabela de Conversa da seção 15.5, pela `phase`
 * que o store calcula dos eventos SSE (`applyStreamEvent`, em
 * `features/ask/model.ts`):
 * - `waiting`: três linhas de skeleton e o caret, até o primeiro token.
 * - `streaming`: o texto chegando, com o caret no fim.
 * - `done`: texto, fontes e ações. O `outcome` acrescenta o badge de
 *   abstenção, substituição ou indisponível, ou troca tudo pelo alerta de
 *   recusa médica.
 * - `cancelled`: "Interrompida." e Tentar de novo.
 * - `error`: a mensagem, o `RequestIdCopy` e Tentar de novo.
 *
 * Acessibilidade: o `article` fica com `aria-busy` durante a geração
 * (seção 15.8); a resposta inteira é anunciada pela região live do
 * `ChatThread`, não por este componente. Recusa e erro usam
 * `role="alert"`. Os chips movem o foco para a fonte citada.
 *
 * Movimento (seção 16.3), sempre pelos presets, que decidem o movimento
 * reduzido:
 * - M6: `enterAssistant` faz o `autoAlpha` do contêiner ao montar. O
 *   turno monta já no envio, em `waiting`; o catálogo cita o evento
 *   `meta` como gatilho.
 * - M8: `enterCitations` faz os chips entrarem com `stagger` de 0,04 s.
 * - M9: `replaceAnswer` esmaece o rascunho (`data-outgoing`) e mostra a
 *   resposta segura (`data-incoming`) quando chega o evento `replace`.
 */
import { useRef, useState } from "react"
import { Copy, ThumbsDown, ThumbsUp } from "lucide-react"

import { CitationChip } from "@/components/patterns/citation-chip.tsx"
import { OutcomeBadge } from "@/components/patterns/outcome-badge.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { SourceList } from "@/components/patterns/source-list.tsx"
import { StreamingCaret } from "@/components/patterns/streaming-caret.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Skeleton } from "@/components/ui/skeleton.tsx"
import type {
  AssistantPhase,
  CitationView,
  FeedbackState,
} from "@/features/ask/types.ts"
import { pt } from "@/i18n/pt.ts"
import { useGSAP } from "@/motion/gsap.ts"
import { useMotion } from "@/motion/MotionProvider.tsx"
import { presets } from "@/motion/presets.ts"

/** Uma resposta do assistente, em qualquer fase. */
export function AssistantMessage({
  phase,
  text,
  outgoing,
  citations,
  outcome,
  replaced,
  errorMessage,
  requestId,
  feedback,
  canAnswer,
  onFeedback,
  onRetry,
}: {
  phase: AssistantPhase
  text: string
  /** Rascunho que o evento `replace` substituiu; sai com M9. */
  outgoing: string | null
  citations: CitationView[]
  /** Desfecho do `done`, como `answered`, `abstained` ou `refused`. */
  outcome: string | null
  /** O texto atual é a resposta segura que tomou o lugar do rascunho. */
  replaced: boolean
  errorMessage: string | null
  requestId: string | null
  /** Avaliação dada (`1` ou `-1`), `"locked"` se já avaliada, ou `null`. */
  feedback: FeedbackState
  /** Mostra as ações: só numa resposta concluída e já gravada. */
  canAnswer: boolean
  onFeedback: (rating: 1 | -1) => void
  onRetry: () => void
}) {
  const rootRef = useRef<HTMLElement>(null)
  const { reduced } = useMotion()
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const busy = phase === "waiting" || phase === "streaming"
  // Muda quando chega uma citação nova, e só então M8 roda de novo.
  const citationKey = citations.map((citation) => citation.chunkId).join(",")

  // M6. Sem dependências: roda uma vez, quando o turno monta.
  useGSAP(
    () => {
      presets.enterAssistant(rootRef.current, reduced)
    },
    { scope: rootRef }
  )

  // M9. O preset acha `data-outgoing` e `data-incoming` dentro da raiz.
  useGSAP(
    () => {
      if (!replaced) {
        return
      }
      presets.replaceAnswer(rootRef.current, reduced)
    },
    { scope: rootRef, dependencies: [replaced, reduced] }
  )

  // M8. Os chips ficam no texto; o `querySelectorAll` parte da raiz.
  useGSAP(
    () => {
      const chips = rootRef.current?.querySelectorAll("[data-citation]")
      if (!chips || chips.length === 0) {
        return
      }
      presets.enterCitations(chips, reduced)
    },
    { scope: rootRef, dependencies: [citationKey, reduced] }
  )

  /**
   * Abre a lista de fontes e põe o foco na fonte do chip clicado. O foco
   * espera o próximo quadro, porque o item da lista só existe depois que
   * o React renderiza a lista aberta.
   */
  function openSource(chunkId: string) {
    setSourcesOpen(true)
    window.requestAnimationFrame(() => {
      document.getElementById(`source-${chunkId}`)?.focus()
    })
  }

  return (
    <article
      ref={rootRef}
      // Seção 15.8: a mensagem fica ocupada enquanto o texto chega.
      aria-busy={busy}
      data-phase={phase}
      className="flex max-w-full flex-col gap-3"
    >
      {phase === "waiting" ? <WaitingLines /> : null}
      {phase === "streaming" || phase === "done" ? (
        <AnswerBody
          phase={phase}
          text={text}
          outgoing={outgoing}
          citations={citations}
          outcome={outcome}
          replaced={replaced}
          sourcesOpen={sourcesOpen}
          onOpenChange={setSourcesOpen}
          onSelect={openSource}
        />
      ) : null}
      {phase === "cancelled" ? <Interrupted onRetry={onRetry} /> : null}
      {phase === "error" ? (
        <StreamError
          message={errorMessage}
          requestId={requestId}
          onRetry={onRetry}
        />
      ) : null}
      {phase === "done" && canAnswer ? (
        <AnswerActions
          text={text}
          feedback={feedback}
          onFeedback={onFeedback}
        />
      ) : null}
    </article>
  )
}

/**
 * Espera pelo primeiro token: três linhas de skeleton e o caret (seção
 * 15.5). Os blocos são `aria-hidden`; o texto em `sr-only` diz
 * "Preparando a resposta".
 */
function WaitingLines() {
  return (
    <div className="flex flex-col gap-2">
      <span className="sr-only">{pt.ask.waiting}</span>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-4/5" />
      <Skeleton className="h-4 w-2/3" />
      <StreamingCaret />
    </div>
  )
}

/**
 * Corpo da resposta em fluxo ou concluída.
 *
 * 1. Recusa médica concluída: só o alerta, com o badge e o texto fixo de
 *    orientação médica que a API manda (seção 10.1).
 * 2. Rascunho substituído: o texto antigo fica por cima, em posição
 *    absoluta e `aria-hidden`, até M9 esmaecê-lo.
 * 3. Badges do desfecho: substituída (com a nota), abstenção (inclui
 *    `grounding_failed`) ou indisponível (`degraded` e `error`).
 * 4. O texto, com os chips no lugar dos marcadores e o caret no fluxo.
 * 5. A lista de fontes, só no `done`.
 */
function AnswerBody({
  phase,
  text,
  outgoing,
  citations,
  outcome,
  replaced,
  sourcesOpen,
  onOpenChange,
  onSelect,
}: {
  phase: "streaming" | "done"
  text: string
  outgoing: string | null
  citations: CitationView[]
  outcome: string | null
  replaced: boolean
  sourcesOpen: boolean
  onOpenChange: (open: boolean) => void
  onSelect: (chunkId: string) => void
}) {
  // 1. O fundo é o par de status da seção 14.2, `--danger` a 15%.
  if (phase === "done" && outcome === "refused") {
    return (
      <div
        role="alert"
        className="flex flex-col gap-3 rounded-2xl border border-danger bg-[color-mix(in_oklab,var(--danger)_15%,transparent)] p-4"
      >
        <OutcomeBadge kind="refused" />
        <p className="text-message whitespace-pre-wrap text-foreground">
          {text}
        </p>
      </div>
    )
  }

  return (
    <div className="relative flex flex-col gap-3">
      {/* 2. Cobre o texto novo durante a troca, sem empurrar o layout. */}
      {replaced && outgoing ? (
        <p
          data-outgoing
          aria-hidden="true"
          className="absolute inset-x-0 top-0 text-message whitespace-pre-wrap text-foreground"
        >
          {outgoing}
        </p>
      ) : null}
      {/* 3. Abstenção e substituição têm badge e texto (seção 15.6). */}
      {phase === "done" && replaced ? (
        <>
          <p className="text-body text-foreground">{pt.ask.replacedNote}</p>
          <OutcomeBadge kind="replaced" />
        </>
      ) : null}
      {phase === "done" &&
      !replaced &&
      (outcome === "abstained" || outcome === "grounding_failed") ? (
        <OutcomeBadge kind="abstained" />
      ) : null}
      {phase === "done" && (outcome === "degraded" || outcome === "error") ? (
        <OutcomeBadge kind="unavailable" />
      ) : null}
      {/* 4. Tokens não são animados um a um (M6): o texto só cresce. */}
      <p
        data-incoming
        className="text-message whitespace-pre-wrap text-foreground"
      >
        <AnswerPieces text={text} citations={citations} onSelect={onSelect} />
        {phase === "streaming" ? <StreamingCaret /> : null}
      </p>
      {/* 5. */}
      {phase === "done" ? (
        <SourceList
          citations={citations}
          open={sourcesOpen}
          onOpenChange={onOpenChange}
        />
      ) : null}
    </div>
  )
}

/**
 * Corta o texto nos marcadores de citação e põe um `CitationChip` no
 * lugar de cada número. Um grupo com um índice sem citação conhecida fica
 * como texto, para não apontar para uma fonte que não existe. O teste
 * `assistant-message.test.tsx` cobre os dois casos.
 */
function AnswerPieces({
  text,
  citations,
  onSelect,
}: {
  text: string
  citations: CitationView[]
  onSelect: (chunkId: string) => void
}) {
  // [2] e também o grupo [2, 3], que o modelo às vezes escreve.
  const pieces = text.split(/(\[\d+(?:\s*[,;]\s*\d+)*\])/g)
  return pieces.map((piece, index) => {
    const match = /^\[([\d\s,;]+)\]$/.exec(piece)
    if (!match) {
      return <span key={`${index}-${piece}`}>{piece}</span>
    }
    const found = match[1]
      .split(/[,;]/)
      .map((raw) => Number(raw.trim()))
      .map((citationIndex) => ({
        citationIndex,
        citation: citations.find((item) => item.index === citationIndex),
      }))
    if (found.some((item) => !item.citation)) {
      return <span key={`${index}-${piece}`}>{piece}</span>
    }
    return found.map(({ citationIndex, citation }) =>
      citation ? (
        <CitationChip
          key={`${citation.chunkId}-${index}-${citationIndex}`}
          index={citationIndex}
          onSelect={() => {
            onSelect(citation.chunkId)
          }}
        />
      ) : null
    )
  })
}

/** Resposta parada pelo Stop: "Interrompida." e Tentar de novo (15.5). */
function Interrupted({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3">
      <p className="text-message text-foreground">{pt.ask.interrupted}</p>
      <Button type="button" className="min-h-11 md:min-h-8" onClick={onRetry}>
        {pt.ask.retry}
      </Button>
    </div>
  )
}

/**
 * Erro do fluxo: a mensagem amigável, o `request_id` copiável e Tentar de
 * novo, sem beco sem saída (seções 15.1 e 15.5). `role="alert"` anuncia
 * o erro assim que ele aparece.
 */
function StreamError({
  message,
  requestId,
  onRetry,
}: {
  message: string | null
  requestId: string | null
  onRetry: () => void
}) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3">
      <p className="text-message text-foreground">
        {message || pt.ask.couldNotFinish}
      </p>
      {requestId ? <RequestIdCopy requestId={requestId} /> : null}
      <Button type="button" className="min-h-11 md:min-h-8" onClick={onRetry}>
        {pt.ask.retry}
      </Button>
    </div>
  )
}

/**
 * Ações depois do `done`: Útil, Não útil e Copiar resposta (seção 15.5).
 * A avaliação sobe pelo `onFeedback` até o hook da conversa, que a grava
 * na API; a seção 15.6 leva esse feedback à fila de anotação do LangSmith.
 *
 * Os botões de avaliação usam `aria-pressed` e ficam desabilitados depois
 * de uma avaliação. Desabilitar o botão focado manda o foco para o
 * `body`; a Etapa 14.3 do plano corrige isso. Alvos de 44 px no celular
 * (seção 15.8).
 */
function AnswerActions({
  text,
  feedback,
  onFeedback,
}: {
  text: string
  feedback: FeedbackState
  onFeedback: (rating: 1 | -1) => void
}) {
  const [copied, setCopied] = useState(false)
  const rated = feedback !== null

  // Sem permissão de área de transferência, o rótulo continua "Copiar".
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant={feedback === 1 ? "default" : "outline"}
          className="min-h-11 md:min-h-8"
          aria-pressed={feedback === 1}
          disabled={rated}
          onClick={() => {
            onFeedback(1)
          }}
        >
          <ThumbsUp />
          {pt.ask.useful}
        </Button>
        <Button
          type="button"
          variant={feedback === -1 ? "default" : "outline"}
          className="min-h-11 md:min-h-8"
          aria-pressed={feedback === -1}
          disabled={rated}
          onClick={() => {
            onFeedback(-1)
          }}
        >
          <ThumbsDown />
          {pt.ask.notUseful}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-11 md:min-h-8"
          onClick={() => {
            void copy()
          }}
        >
          <Copy />
          {copied ? pt.ask.copied : pt.ask.copy}
        </Button>
      </div>
      {/* `locked`: a API respondeu 409, a resposta já tinha avaliação. */}
      {feedback === "locked" ? (
        <p className="text-caption text-muted-foreground">
          {pt.ask.alreadyRated}
        </p>
      ) : null}
    </div>
  )
}
