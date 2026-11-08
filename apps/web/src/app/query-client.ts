/**
 * O cache do TanStack Query, num objeto só para o app inteiro.
 *
 * Junto com `lib/api`, é o Model do frontend (SDD 13.2): guarda o que o
 * servidor respondeu, por chave de consulta, como `["me"]` para o perfil.
 *
 * Quem usa: `providers.tsx`, que o entrega aos hooks; os guards de
 * `guards.ts`, que rodam fora do React e por isso importam o objeto
 * direto; os hooks de feature que gravam ou limpam o cache, como
 * `useSignIn` e `useSignOut`; e `test/setup.ts`, que o limpa depois de
 * cada teste.
 */
import { QueryClient } from "@tanstack/react-query"

/**
 * O cliente único do cache.
 *
 * `retry: false` tira a nova tentativa automática: no padrão, o TanStack
 * Query tenta de novo três vezes, e aqui uma consulta que falha mostra o
 * erro na hora. `refetchOnWindowFocus: false` não relê as consultas quando
 * a aba volta ao foco.
 *
 * O `staleTime` fica no padrão, zero: o dado vale como velho assim que
 * chega, e cada componente que passa a usar a consulta dispara uma
 * releitura em segundo plano. O `ensureQueryData` dos guards não relê:
 * devolve o que já está no cache.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
})
