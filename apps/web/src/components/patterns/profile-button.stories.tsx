import type { Meta, StoryObj } from "@storybook/react-vite"

import { ProfileButton } from "@/components/patterns/profile-button.tsx"

const meta = {
  title: "Patterns/ProfileButton",
  component: ProfileButton,
} satisfies Meta<typeof ProfileButton>

export default meta

type Story = StoryObj<typeof meta>

export const Expandido: Story = {
  args: { collapsed: false },
}

export const Recolhido: Story = {
  args: { collapsed: true },
}

export const MenuAberto: Story = {
  args: { collapsed: false, defaultOpen: true },
}

export const ComSessao: Story = {
  args: {
    collapsed: false,
    defaultOpen: true,
    name: "Ana",
    onSignOut: () => undefined,
  },
}

export const Saindo: Story = {
  args: {
    collapsed: false,
    defaultOpen: true,
    name: "Ana",
    onSignOut: () => undefined,
    signingOut: true,
  },
}

export const FalhaAoSair: Story = {
  args: {
    collapsed: false,
    name: "Ana",
    onSignOut: () => undefined,
    signOutError: "Não foi possível sair. Tente de novo.",
  },
}
