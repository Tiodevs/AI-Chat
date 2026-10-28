import type { Meta, StoryObj } from "@storybook/react-vite"

import { UserMessage } from "@/components/patterns/user-message.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/UserMessage",
  component: UserMessage,
  args: { text: pt.ask.suggestions[0].question, privacy: false },
} satisfies Meta<typeof UserMessage>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex max-w-xl flex-col gap-6">
      <UserMessage text={pt.ask.suggestions[0].question} privacy={false} />
      <UserMessage text={pt.ask.suggestions[1].question} privacy={false} />
      <UserMessage text="" privacy />
      <UserMessage
        text="Onde deixo o carro se a garagem da Harbor Street estiver cheia e eu chegar depois das 18 horas?"
        privacy={false}
      />
    </div>
  ),
}
