import type { Meta, StoryObj } from "@storybook/react-vite"

import { DataTable, type DataTableColumn } from "@/components/patterns/data-table.tsx"
import { Badge } from "@/components/ui/badge.tsx"
import { pt } from "@/i18n/pt.ts"

type Row = { id: string; title: string; version: string; ready: boolean }

const rows: Row[] = [
  { id: "1", title: "Estacionamento", version: "v2", ready: true },
  { id: "2", title: "Horário de visita", version: "v1", ready: false },
]

const columns: DataTableColumn<Row>[] = [
  { key: "title", header: pt.documents.table.title, rowHeader: true, cell: (row) => row.title },
  { key: "version", header: pt.documents.table.activeVersion, cell: (row) => row.version },
  {
    key: "status",
    header: pt.documents.table.status,
    cell: (row) =>
      row.ready ? (
        <Badge variant="success">{pt.documents.status.ready}</Badge>
      ) : (
        <Badge variant="info">{pt.documents.status.processing}</Badge>
      ),
  },
]

const meta = {
  title: "Patterns/DataTable",
  component: DataTable<Row>,
  args: {
    caption: pt.documents.table.caption,
    columns,
    rows,
    rowKey: (row: Row) => row.id,
    empty: pt.documents.table.empty,
  },
} satisfies Meta<typeof DataTable<Row>>

export default meta

type Story = StoryObj<typeof meta>

export const ComLinhas: Story = {}

export const Carregando: Story = { args: { loading: true } }

export const Vazia: Story = { args: { rows: [] } }
