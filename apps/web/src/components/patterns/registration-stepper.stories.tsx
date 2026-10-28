import type { Meta, StoryObj } from "@storybook/react-vite"

import { RegistrationStepper } from "@/components/patterns/registration-stepper.tsx"
import { registrationPhases } from "@/features/registration/model.ts"

const meta = {
  title: "Patterns/RegistrationStepper",
  component: RegistrationStepper,
} satisfies Meta<typeof RegistrationStepper>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  args: { phase: "details" },
  render: () => (
    <div className="flex max-w-3xl flex-col gap-8">
      {registrationPhases.map((phase) => (
        <RegistrationStepper key={phase} phase={phase} />
      ))}
    </div>
  ),
}
