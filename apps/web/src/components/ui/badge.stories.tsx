import type { Meta, StoryObj } from "@storybook/react-vite"

import { Badge } from "@/components/ui/badge.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Badge",
  component: Badge,
  args: { children: pt.documents.status.ready },
} satisfies Meta<typeof Badge>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Badge variant="info">
        <Spinner aria-hidden="true" />
        {pt.documents.status.processing}
      </Badge>
      <Badge variant="success">{pt.documents.status.ready}</Badge>
      <Badge variant="danger">{pt.documents.status.failed}</Badge>
      <Badge variant="warning">{pt.ask.outcomes.abstained}</Badge>
      <Badge variant="secondary">{pt.documents.status.archived}</Badge>
      <Badge variant="outline">{pt.documents.table.noActive}</Badge>
    </div>
  ),
}
