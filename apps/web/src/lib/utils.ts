/**
 * `cn`, que junta classes do Tailwind e resolve os conflitos entre elas.
 *
 * Vem do pacote `cn`, que substitui o par `clsx` e `tailwind-merge` com a
 * mesma saída. Aceita textos, listas e objetos condicionais, e entre
 * classes que disputam a mesma propriedade fica a última:
 * `cn("px-2", "px-4")` dá `px-4`. O shadcn/ui procura o `cn` neste caminho
 * (`components.json`, alias `utils`).
 *
 * Cuidado: o `cn` não conhece as utilidades de texto da seção 14.3
 * (`text-caption`, `text-label`, `text-body`, `text-message`,
 * `text-title`, `text-metric` e `text-display`, de `styles/globals.css`)
 * e as trata como cor de texto. Por isso `cn("text-body text-foreground")`
 * devolve só `text-foreground`, e o tamanho se perde.
 *
 * Quem usa: a casca (`app/shell.tsx`), os componentes de
 * `components/patterns` que juntam classes e a visão geral do admin. Os de
 * `components/ui` importam `cn` direto do pacote.
 */
export { cn } from "cn"
