import type { Meta, StoryObj } from "@storybook/react-vite"

import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Card",
  component: Card,
} satisfies Meta<typeof Card>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <Card className="w-72 rounded-card shadow-none ring-border">
      <CardHeader>
        <CardTitle className="text-label">{pt.notice.title}</CardTitle>
        <CardDescription className="text-caption text-subtle-foreground">
          {pt.notice.body}
        </CardDescription>
      </CardHeader>
    </Card>
  ),
}
