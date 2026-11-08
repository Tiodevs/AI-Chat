/**
 * Os provedores globais do app: o cache do TanStack Query e o contexto de
 * movimento.
 *
 * Quem usa: `main.tsx`, a pré-visualização do Storybook
 * (`.storybook/preview.tsx`) e os testes que montam telas inteiras, como
 * `shell.test.tsx`. Usa `query-client.ts` e `motion/MotionProvider.tsx`.
 * SDD 13.2 (o cache faz parte do Model) e 16.4 (movimento reduzido).
 */
import type { ReactNode } from "react"
import { QueryClientProvider } from "@tanstack/react-query"

import { queryClient } from "@/app/query-client.ts"
import { MotionProvider } from "@/motion/MotionProvider.tsx"

/**
 * Envolve o app com o `QueryClientProvider`, que entrega o cache aos hooks
 * `useQuery`, e com o `MotionProvider`, que entrega o `useMotion` aos
 * componentes que animam. O cliente é o mesmo objeto que os guards de rota
 * usam fora do React, então o que um guard lê fica no cache das telas.
 */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MotionProvider>
        {children}
      </MotionProvider>
    </QueryClientProvider>
  )
}
