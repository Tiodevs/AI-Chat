import type { Meta, StoryObj } from "@storybook/react-vite"

import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Tabs",
  component: Tabs,
} satisfies Meta<typeof Tabs>

export default meta

type Story = StoryObj<typeof meta>

function Example({ focus = false }: { focus?: boolean }) {
  return (
    <Tabs defaultValue="profile" className="w-96">
      <TabsList aria-label={pt.account.tabsLabel}>
        <TabsTrigger value="profile" autoFocus={focus}>
          {pt.account.tabs.profile}
        </TabsTrigger>
        <TabsTrigger value="conversations">
          {pt.account.tabs.conversations}
        </TabsTrigger>
        <TabsTrigger value="privacy" disabled>
          {pt.account.tabs.privacy}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="profile">
        <p className="text-body text-foreground">{pt.account.tabs.profile}</p>
      </TabsContent>
      <TabsContent value="conversations">
        <p className="text-body text-foreground">
          {pt.account.conversations.empty}
        </p>
      </TabsContent>
    </Tabs>
  )
}

export const Estados: Story = {
  render: () => <Example />,
}

export const Foco: Story = {
  render: () => <Example focus />,
}
