/**
 * Peças de tabela do shadcn/ui, sem mudança: `<table>` e classes, sem
 * Radix.
 *
 * Usadas pelo `DataTable`, que monta as tabelas de documentos, conversas
 * e pedidos de titular do admin. As bordas usam `--border`, e o hover da
 * linha usa `--muted` (seção 14.7). Seção 14.6.
 */
import * as React from "react"
import { cn } from "cn"

/**
 * Tabela dentro de um `div` com rolagem horizontal: colunas largas rolam
 * dentro da tabela, sem alargar a página no celular.
 */
function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div
      data-slot="table-container"
      className="relative w-full overflow-x-auto"
    >
      <table
        data-slot="table"
        className={cn("w-full caption-bottom text-sm", className)}
        {...props}
      />
    </div>
  )
}

/** `<thead>`, com borda embaixo das linhas do cabeçalho. */
function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("[&_tr]:border-b", className)}
      {...props}
    />
  )
}

/** `<tbody>`, sem a borda da última linha. */
function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("[&_tr:last-child]:border-0", className)}
      {...props}
    />
  )
}

/** `<tfoot>` com fundo `--muted` a 50%. Sem uso nas telas. */
function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(
        "border-t bg-muted/50 font-medium [&>tr]:last:border-b-0",
        className
      )}
      {...props}
    />
  )
}

/**
 * `<tr>` com hover em `--muted` a 50%. `data-state="selected"` pinta a
 * linha de `--muted`, e `has-aria-expanded` destaca a linha com um botão
 * aberto.
 */
function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "border-b transition-colors hover:bg-muted/50 has-aria-expanded:bg-muted/50 data-[state=selected]:bg-muted",
        className
      )}
      {...props}
    />
  )
}

/**
 * `<th>`. O chamador passa `scope="col"` ou `scope="row"`, que diz ao
 * leitor de tela se a célula é título de coluna ou de linha.
 */
function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "h-10 px-2 text-left align-middle font-medium whitespace-nowrap text-foreground [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

/** `<td>`. Sem quebra de linha por padrão; o `DataTable` a liga. */
function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "p-2 align-middle whitespace-nowrap [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

/**
 * `<caption>`, o nome da tabela. O `DataTable` a esconde com `sr-only`:
 * ela fica só para o leitor de tela, que a anuncia ao entrar na tabela.
 */
function TableCaption({
  className,
  ...props
}: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-4 text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
