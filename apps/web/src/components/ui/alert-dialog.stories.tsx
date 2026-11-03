import type { Meta, StoryObj } from "@storybook/react-vite"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog.tsx"
import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/AlertDialog",
  component: AlertDialog,
} satisfies Meta<typeof AlertDialog>

export default meta

type Story = StoryObj<typeof meta>

function Content() {
  return (
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>
          {pt.account.privacy.deleteDialogTitle}
        </AlertDialogTitle>
        <AlertDialogDescription>
          {pt.account.privacy.deleteDialogBody}
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel>{pt.account.privacy.deleteCancel}</AlertDialogCancel>
        <AlertDialogAction>{pt.account.privacy.deleteConfirm}</AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  )
}

export const Aberto: Story = {
  render: () => (
    <AlertDialog open>
      <Content />
    </AlertDialog>
  ),
}

export const Fechado: Story = {
  render: () => (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="destructive">{pt.account.privacy.deleteButton}</Button>
      </AlertDialogTrigger>
      <Content />
    </AlertDialog>
  ),
}
