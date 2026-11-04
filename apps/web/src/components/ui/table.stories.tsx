import type { Meta, StoryObj } from "@storybook/react-vite"

import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "UI/Table",
  component: Table,
} satisfies Meta<typeof Table>

export default meta

type Story = StoryObj<typeof meta>

export const Estados: Story = {
  render: () => (
    <Table className="max-w-xl">
      <TableCaption>{pt.documents.table.caption}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead scope="col">{pt.documents.table.title}</TableHead>
          <TableHead scope="col">{pt.documents.table.activeVersion}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>Estacionamento</TableCell>
          <TableCell>v2</TableCell>
        </TableRow>
        <TableRow data-state="selected">
          <TableCell>Horário de visita</TableCell>
          <TableCell>v1</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
}
