import type { Meta, StoryObj } from "@storybook/react-vite"

import { ChatErrorNotice } from "@/components/patterns/chat-error-notice.tsx"
import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/ChatErrorNotice",
  component: ChatErrorNotice,
  args: {
    title: pt.registration.errorTitle,
    message: pt.couldNotContinue,
    requestId: null,
  },
} satisfies Meta<typeof ChatErrorNotice>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex max-w-xl flex-col gap-6">
      <ChatErrorNotice
        title={pt.registration.errorTitle}
        message={pt.couldNotContinue}
        requestId={null}
        onRetry={() => undefined}
        onDismiss={() => undefined}
      />
      <ChatErrorNotice
        title={pt.registration.errorTitle}
        message={pt.registration.unavailable}
        requestId="01JBX4Y6Z8W2Q5N7R3T9V1K0M"
        onRetry={() => undefined}
        onDismiss={() => undefined}
      >
        <Button variant="link" className="h-11 px-0 md:h-8">
          {pt.registration.useForm}
        </Button>
      </ChatErrorNotice>
      <ChatErrorNotice
        title={pt.registration.errorTitle}
        message={pt.couldNotContinue}
        requestId={null}
      />
    </div>
  ),
}
