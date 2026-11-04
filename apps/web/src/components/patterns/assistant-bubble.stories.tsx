import type { Meta, StoryObj } from "@storybook/react-vite"

import { AssistantBubble } from "@/components/patterns/assistant-bubble.tsx"

const meta = {
  title: "Patterns/AssistantBubble",
  component: AssistantBubble,
  args: { text: "Olá! Para começar, qual é o seu nome completo?" },
} satisfies Meta<typeof AssistantBubble>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex max-w-xl flex-col gap-6">
      <AssistantBubble text="Olá! Para começar, qual é o seu nome completo?" />
      <AssistantBubble text="Obrigado, Ana. Qual e-mail você quer usar para entrar? Ele também serve para receber um aviso sobre a conta, se algo mudar." />
      <AssistantBubble typing />
    </div>
  ),
}
