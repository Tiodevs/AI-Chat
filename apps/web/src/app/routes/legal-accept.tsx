/**
 * Rota `/legal/accept`, o novo aceite dos Termos de Uso e do Aviso de
 * Privacidade depois de uma versão nova (seção 13.3).
 *
 * Liga o controller `useLegalAccept` à tela `LegalAcceptScreen` (SDD
 * 13.2), que grava o aceite e volta para o `returnTo`. O guard
 * `requireSession` exige só a sessão: o aceite pendente é o que esta
 * página resolve.
 */
import { useQuery } from "@tanstack/react-query"

import { LegalAcceptScreen } from "@/features/account/legal-accept-screen.tsx"
import { useLegalAccept } from "@/features/account/useLegalAccept.ts"
import { meQuery, type Me } from "@/features/auth/useSession.ts"

/**
 * Separa o hook da checagem de `me`: um hook não pode vir depois de um
 * `return` condicional, e `useLegalAccept` precisa do perfil.
 */
function LegalAcceptPage({ me }: { me: Me }) {
  const model = useLegalAccept(me)
  return <LegalAcceptScreen {...model} />
}

/** Lê do cache o perfil que o guard carregou. Sem perfil, não mostra nada. */
export function Component() {
  const me = useQuery(meQuery).data
  if (!me) {
    return null
  }
  return <LegalAcceptPage me={me} />
}
