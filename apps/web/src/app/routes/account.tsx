/**
 * Rota `/account`, a conta do membro, com as abas Perfil, Conversas e
 * Privacidade (seção 15.5).
 *
 * Liga o controller `useAccount` à tela `AccountScreen` (SDD 13.2). O
 * guard `requireUser` de `router.tsx` exige sessão e aceite antes de a
 * página abrir e deixa o perfil no cache.
 */
import { useQuery } from "@tanstack/react-query"

import { AccountScreen } from "@/features/account/account-screen.tsx"
import { useAccount } from "@/features/account/useAccount.ts"
import { meQuery, type Me } from "@/features/auth/useSession.ts"

/**
 * Separa o hook da checagem de `me`: um hook não pode vir depois de um
 * `return` condicional, e `useAccount` precisa do perfil.
 */
function AccountPage({ me }: { me: Me }) {
  const model = useAccount(me)
  return <AccountScreen {...model} />
}

/**
 * Lê o perfil do cache, que o guard já preencheu. Sem perfil, não mostra
 * nada: é o que acontece se a releitura de `GET /v1/me` voltar sem sessão.
 * A página fica vazia em vez de levar ao login; a Etapa 14.1 corrige.
 */
export function Component() {
  const me = useQuery(meQuery).data
  if (!me) {
    return null
  }
  return <AccountPage me={me} />
}
