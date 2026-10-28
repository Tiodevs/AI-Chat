import type { Meta, StoryObj } from "@storybook/react-vite"

import { Skeleton } from "@/components/ui/skeleton.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Skeleton",
  component: Skeleton,
} satisfies Meta<typeof Skeleton>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <div className="flex max-w-md flex-col gap-6">
      <div
        className="flex flex-col gap-2"
        aria-busy="true"
        aria-label={pt.ask.waiting}
      >
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-2/3" />
      </div>
      <Skeleton className="h-11 w-full" />
      <Skeleton className="size-11 rounded-full" />
    </div>
  ),
}
