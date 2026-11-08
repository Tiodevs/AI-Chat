/**
 * Tabela genérica das telas de admin: carregando, vazia e com linhas
 * (seções 14.6 e 14.7).
 *
 * Monta as tabelas de documentos (`/admin/documents`), de conversas
 * (`/admin/quality`) e de pedidos de titular (`/admin/privacy`) a partir
 * de uma lista de colunas: cada coluna diz o cabeçalho e como desenhar a
 * célula de uma linha. Filtros, ordem e ações ficam nas telas. É feita à
 * mão sobre o `Table` do shadcn; a seção 13.1 cita o TanStack Table, que
 * não está nas dependências.
 *
 * Estados: carregando (`aria-busy` e linhas de skeleton no formato das
 * colunas), vazia (uma célula que ocupa todas as colunas) e com linhas.
 *
 * Acessibilidade: a legenda da tabela fica em `sr-only`, os cabeçalhos
 * têm `scope="col"`, e a coluna marcada com `rowHeader` vira `<th
 * scope="row">`, para o leitor de tela anunciar o título da linha junto
 * de cada célula.
 */
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

/** Uma coluna: a chave do React, o cabeçalho e o desenho da célula. */
export type DataTableColumn<Row> = {
  key: string
  header: string
  cell: (row: Row) => ReactNode
  /** Classes extras do cabeçalho e das células, como a largura. */
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
  /** `undefined` antes da primeira resposta; `[]` mostra o vazio. */
  rows: Row[] | undefined
  /** Chave estável de cada linha, como o id do registro. */
  rowKey: (row: Row) => string
  loading?: boolean
  /** O que dizer quando não há linhas. */
  empty: ReactNode
  /** Quantas linhas de skeleton mostrar enquanto carrega. */
  skeletonRows?: number
}) {
  // A moldura repete a do `Card` (`rounded-xl`, borda de `--foreground` a
  // 10%), e não o raio de 16 px da seção 14.4.
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
          {/* Carregando: `skeletonRows` linhas de skeleton no formato das */}
          {/* colunas (seção 14.7), cada uma com o nome "Carregando". */}
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
          {/* Com linhas: hover em `--muted` (seção 14.7). */}
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
