import type { Meta, StoryObj } from "@storybook/react-vite"

import { AttendantMessage } from "@/components/patterns/attendant-message.tsx"

const meta = {
  title: "Patterns/AttendantMessage",
  component: AttendantMessage,
  args: {
    text: "Olá! A visita na enfermaria vai das 11:00 às 20:00. Posso ajudar com mais alguma coisa?",
    redaction: null,
  },
} satisfies Meta<typeof AttendantMessage>

export default meta

type Story = StoryObj<typeof meta>

// Padrão, texto longo com quebra de linha, um link que fica como texto, a
// mensagem removida pela equipe e a apagada pela retenção.
export const Estados: Story = {
  render: () => (
    <div className="flex max-w-xl flex-col gap-6">
      <AttendantMessage
        text="Olá! A visita na enfermaria vai das 11:00 às 20:00."
        redaction={null}
      />
      <AttendantMessage
        text={
          "Para cobrança, ligue para (555) 014-2630.\nO balcão fica no nível 1, dias úteis, das 08:00 às 16:30."
        }
        redaction={null}
      />
      <AttendantMessage
        text="Veja https://exemplo.invalid/pagina: o link aparece como texto."
        redaction={null}
      />
      <AttendantMessage text="[mensagem removida]" redaction="health" />
      <AttendantMessage
        text="[conteúdo do atendimento apagado]"
        redaction="retention"
      />
    </div>
  ),
}
