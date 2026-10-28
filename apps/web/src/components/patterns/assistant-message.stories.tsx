import type { Meta, StoryObj } from "@storybook/react-vite"

import { AssistantMessage } from "@/components/patterns/assistant-message.tsx"
import type { CitationView } from "@/features/ask/types.ts"
import { pt } from "@/i18n/pt.ts"

const citation: CitationView = {
  index: 1,
  documentTitle: "Visitas",
  heading: "Horário",
  chunkId: "00000000-0000-4000-8000-0000000000c1",
}

const answer = "O horário de visita é das 11:00 às 20:00 [1]."

const meta = {
  title: "Patterns/AssistantMessage",
  component: AssistantMessage,
} satisfies Meta<typeof AssistantMessage>

export default meta

type Story = StoryObj<typeof meta>

const quiet = {
  onFeedback: () => undefined,
  onRetry: () => undefined,
}

export const Estados: Story = {
  args: {
    phase: "done",
    text: answer,
    outgoing: null,
    citations: [citation],
    outcome: "answered",
    replaced: false,
    errorMessage: null,
    requestId: null,
    feedback: null,
    canAnswer: true,
    ...quiet,
  },
  render: () => (
    <div className="flex max-w-xl flex-col gap-8">
      <AssistantMessage
        phase="waiting"
        text=""
        outgoing={null}
        citations={[]}
        outcome={null}
        replaced={false}
        errorMessage={null}
        requestId={null}
        feedback={null}
        canAnswer={false}
        {...quiet}
      />
      <AssistantMessage
        phase="streaming"
        text="O horário de visita"
        outgoing={null}
        citations={[]}
        outcome={null}
        replaced={false}
        errorMessage={null}
        requestId={null}
        feedback={null}
        canAnswer={false}
        {...quiet}
      />
      <AssistantMessage
        phase="done"
        text={answer}
        outgoing={null}
        citations={[citation]}
        outcome="answered"
        replaced={false}
        errorMessage={null}
        requestId={null}
        feedback={null}
        canAnswer
        {...quiet}
      />
      <AssistantMessage
        phase="done"
        text={pt.ask.unavailable}
        outgoing={null}
        citations={[]}
        outcome="abstained"
        replaced={false}
        errorMessage={null}
        requestId={null}
        feedback={1}
        canAnswer
        {...quiet}
      />
      <AssistantMessage
        phase="done"
        text="Não posso ajudar com sintomas, diagnóstico ou medicamento."
        outgoing={null}
        citations={[]}
        outcome="refused"
        replaced={false}
        errorMessage={null}
        requestId={null}
        feedback={null}
        canAnswer
        {...quiet}
      />
      <AssistantMessage
        phase="done"
        text={pt.ask.unavailable}
        outgoing="Ligue (555) 019-9999."
        citations={[]}
        outcome="grounding_failed"
        replaced
        errorMessage={null}
        requestId={null}
        feedback={null}
        canAnswer
        {...quiet}
      />
      <AssistantMessage
        phase="cancelled"
        text=""
        outgoing={null}
        citations={[]}
        outcome="cancelled"
        replaced={false}
        errorMessage={null}
        requestId={null}
        feedback={null}
        canAnswer={false}
        {...quiet}
      />
      <AssistantMessage
        phase="error"
        text=""
        outgoing={null}
        citations={[]}
        outcome={null}
        replaced={false}
        errorMessage={pt.ask.couldNotFinish}
        requestId="01JREQUEST"
        feedback={null}
        canAnswer={false}
        {...quiet}
      />
      <AssistantMessage
        phase="done"
        text={pt.ask.unavailable}
        outgoing={null}
        citations={[]}
        outcome="degraded"
        replaced={false}
        errorMessage={null}
        requestId={null}
        feedback="locked"
        canAnswer
        {...quiet}
      />
    </div>
  ),
}
