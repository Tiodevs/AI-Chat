import type { Meta, StoryObj } from "@storybook/react-vite"

import { HandoffOffer } from "@/components/patterns/handoff-offer.tsx"

const meta = {
  title: "Patterns/HandoffOffer",
  component: HandoffOffer,
  args: { availability: "open", onRequest: () => undefined },
} satisfies Meta<typeof HandoffOffer>

export default meta

type Story = StoryObj<typeof meta>

// `open`, enviando, `busy`, `closed` e o bloqueio por abuso. `disabled` não
// mostra nada.
export const Estados: Story = {
  render: () => (
    <div className="flex max-w-xl flex-col gap-6">
      <HandoffOffer availability="open" onRequest={() => undefined} />
      <HandoffOffer availability="open" pending onRequest={() => undefined} />
      <HandoffOffer availability="busy" onRequest={() => undefined} />
      <HandoffOffer availability="closed" onRequest={() => undefined} />
      <HandoffOffer availability="open" blocked onRequest={() => undefined} />
      <HandoffOffer availability="disabled" onRequest={() => undefined} />
    </div>
  ),
}
