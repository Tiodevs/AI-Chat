/**
 * O `AssistantMessage` mostra um chip por fonte quando o modelo agrupa a
 * citação, como `[2, 3]`. FR-2, seções 7.1 (passo Fundamentar) e 14.6 do SDD.
 *
 * Renderiza a mensagem já concluída, com as citações 2 e 3, dentro do
 * `AppProviders`. Um grupo que cita uma fonte desconhecida fica como texto.
 * Projeto `dom` do Vitest: jsdom e `src/test/setup.ts`. Não chama `fetch`, a
 * API nem banco.
 */
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AssistantMessage } from "@/components/patterns/assistant-message.tsx"
import { AppProviders } from "@/app/providers.tsx"
import { pt } from "@/i18n/pt.ts"

/** Uma citação do documento "Acesso" com o `index` dado e um `chunkId`. */
function citation(index: number) {
  return {
    index,
    documentTitle: "Acesso",
    heading: null,
    chunkId: `00000000-0000-4000-8000-00000000000${index}`,
  }
}

/**
 * Renderiza uma resposta `answered`, na fase `done`, com o `text` dado e as
 * citações 2 e 3.
 */
function renderAnswer(text: string) {
  render(
    <AppProviders>
      <AssistantMessage
        phase="done"
        text={text}
        outgoing={null}
        citations={[citation(2), citation(3)]}
        outcome="answered"
        replaced={false}
        errorMessage={null}
        requestId={null}
        feedback={null}
        canAnswer
        onFeedback={() => undefined}
        onRetry={() => undefined}
      />
    </AppProviders>
  )
}

describe("AssistantMessage", () => {
  it("transforma a citação agrupada em um chip por fonte", () => {
    renderAnswer("Fica no lado oeste [2, 3].")
    expect(
      screen.getByRole("button", { name: `${pt.ask.sources} 2` })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: `${pt.ask.sources} 3` })
    ).toBeInTheDocument()
    expect(screen.queryByText(/\[2, 3\]/)).not.toBeInTheDocument()
  })

  it("mantém o texto quando o grupo cita uma fonte desconhecida", () => {
    renderAnswer("Veja [2, 9].")
    expect(screen.getByText(/\[2, 9\]/)).toBeInTheDocument()
  })
})
