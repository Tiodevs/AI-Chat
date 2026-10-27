import type { Meta, StoryObj } from "@storybook/react-vite"

import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { pt } from "@/i18n/pt.ts"

const requestId = "01JREQUEST"

const meta = {
  title: "Patterns/RequestIdCopy",
  component: RequestIdCopy,
  args: { requestId },
} satisfies Meta<typeof RequestIdCopy>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex flex-col gap-6">
      <RequestIdCopy requestId={requestId} />
      <RequestIdCopy requestId={requestId} autoFocus />
      <RequestIdCopy requestId={requestId} initialCopied />
      <RequestIdCopy requestId={requestId} disabled />
      <RequestIdCopy requestId={requestId} busy />
      <div className="flex flex-col gap-2">
        <p className="text-body text-danger">{pt.couldNotContinue}</p>
        <RequestIdCopy requestId={requestId} />
      </div>
    </div>
  ),
}
