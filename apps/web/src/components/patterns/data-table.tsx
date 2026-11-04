import type { ReactNode } from "react"

import { Skeleton } from "@/components/ui/skeleton.tsx"
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
import { cn } from "@/lib/utils.ts"

export type DataTableColumn<Row> = {
  key: string
  header: string
  cell: (row: Row) => ReactNode
  className?: string
  /** O título da linha vira cabeçalho de linha para leitores de tela. */
  rowHeader?: boolean
}

/** Tabela das telas de admin: carregando, vazia e com linhas. SDD 14.6 e 14.7. */
export function DataTable<Row>({
  caption,
  columns,
  rows,
  rowKey,
  loading = false,
  empty,
  skeletonRows = 3,
}: {
  caption: string
  columns: DataTableColumn<Row>[]
  rows: Row[] | undefined
  rowKey: (row: Row) => string
  loading?: boolean
  empty: ReactNode
  skeletonRows?: number
}) {
  return (
    <div className="overflow-hidden rounded-xl bg-card ring-1 ring-foreground/10">
      <Table aria-busy={loading || undefined}>
        <TableCaption className="sr-only">{caption}</TableCaption>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {columns.map((column) => (
              <TableHead
                key={column.key}
                scope="col"
                className={cn("px-4 text-label text-muted-foreground", column.className)}
              >
                {column.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading
            ? Array.from({ length: skeletonRows }, (_, index) => (
                <TableRow key={`skeleton-${String(index)}`} aria-label={pt.loading}>
                  {columns.map((column) => (
                    <TableCell key={column.key} className="px-4 py-3">
                      <Skeleton className="h-4 w-full max-w-40" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            : null}
          {!loading && rows?.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell
                colSpan={columns.length}
                className="px-4 py-8 text-center whitespace-normal text-muted-foreground"
              >
                {empty}
              </TableCell>
            </TableRow>
          ) : null}
          {!loading
            ? rows?.map((row) => (
                <TableRow key={rowKey(row)} className="hover:bg-muted">
                  {columns.map((column) =>
                    column.rowHeader ? (
                      <TableHead
                        key={column.key}
                        scope="row"
                        className={cn(
                          "px-4 py-3 font-medium whitespace-normal text-foreground-strong",
                          column.className,
                        )}
                      >
                        {column.cell(row)}
                      </TableHead>
                    ) : (
                      <TableCell
                        key={column.key}
                        className={cn("px-4 py-3 align-top whitespace-normal", column.className)}
                      >
                        {column.cell(row)}
                      </TableCell>
                    ),
                  )}
                </TableRow>
              ))
            : null}
        </TableBody>
      </Table>
    </div>
  )
}
