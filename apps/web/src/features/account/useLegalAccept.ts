/**
 * Controlador da tela de novo aceite (`/legal/accept`). Quando a versão dos
 * Termos e do Aviso de Privacidade muda, o membro aceita a versão nova aqui
 * antes de seguir para onde ia.
 *
 * Camada: controller (SDD 13.2). Quem usa: `app/routes/legal-accept.tsx`,
 * que passa o `me` do cache e entrega o retorno a `LegalAcceptScreen`. Quem
 * manda o membro para cá é a guarda `requireUser` das rotas protegidas e a
 * tela de entrar. A própria rota usa `requireSession`, que exige sessão sem
 * olhar o aceite: com `requireUser`, a tela redirecionaria para si mesma.
 *
 * Usa `legalVersionsQuery` (`features/privacy/useLegalVersions.ts`),
 * `safeReturnTo` (`features/auth/return-to.ts`), o cliente `api` e o
 * `queryClient`. SDD 11.11 (versão dos documentos) e 13.3 (novo aceite).
 */
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate, useSearchParams } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { safeReturnTo } from "@/features/auth/return-to.ts"
import { meQuery, type Me } from "@/features/auth/useSession.ts"
import { legalVersionsQuery } from "@/features/privacy/useLegalVersions.ts"
import { api } from "@/lib/api/client.ts"

import { failureFrom, termsPurpose, type SubmitFailure } from "./model.ts"

/**
 * Junta o estado e a ação da tela de novo aceite.
 *
 * @param me Perfil do membro. `needs_legal_acceptance` diz se falta aceitar
 *   a versão vigente (SDD 12).
 * @returns A versão vigente dos Termos (`null` enquanto carrega ou se a
 *   leitura falhar), se o aceite falta, o destino seguro, o estado do
 *   pedido, a última falha e a ação `accept`.
 */
export function useLegalAccept(me: Me) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const version = useQuery(legalVersionsQuery)
  const [pending, setPending] = useState(false)
  const [failure, setFailure] = useState<SubmitFailure | null>(null)
  // O `returnTo` vem da URL, então qualquer link pode montá-lo. O
  // `safeReturnTo` só aceita um caminho do próprio site e troca o resto por
  // `/`, para o aceite não virar redirecionamento aberto. A Etapa 15.2 passa
  // essa validação para `new URL`.
  const returnTo = safeReturnTo(params.get("returnTo"))

  /**
   * Grava o aceite e volta ao destino.
   *
   * 1. Envia `PUT /v1/me/consents/terms_and_privacy_notice` com
   *    `{ granted: true }`, o jeito de aceitar a versão nova (SDD 12).
   * 2. Marca `needs_legal_acceptance: false` no perfil em cache. A guarda
   *    `requireUser` lê o cache com `ensureQueryData`: sem essa troca, ela
   *    acharia o aceite pendente e mandaria o membro de volta para cá.
   * 3. Navega para o `returnTo` com `replace`, para o voltar do navegador
   *    não reabrir a tela de aceite.
   */
  async function accept() {
    setPending(true)
    setFailure(null)
    try {
      // 1.
      const result = await api.PUT("/v1/me/consents/{purpose}", {
        params: { path: { purpose: termsPurpose } },
        body: { granted: true },
      })
      if (!result.response.ok) {
        setFailure(failureFrom(result.error, result.response.status))
        return
      }
      // 2.
      queryClient.setQueryData(meQuery.queryKey, {
        ...me,
        needs_legal_acceptance: false,
      })
      // 3.
      await navigate(returnTo, { replace: true })
    } catch {
      // Sem resposta HTTP: status 0 dá a cópia genérica, sem `request_id`.
      setFailure(failureFrom(null, 0))
    } finally {
      setPending(false)
    }
  }

  return {
    // A versão dos Termos. Ela é a mesma do Aviso: as duas vêm da constante
    // `LEGAL_DOCUMENT_VERSION` da API (SDD 11.11).
    version: version.data?.terms ?? null,
    needsAcceptance: me.needs_legal_acceptance,
    returnTo,
    pending,
    failure,
    accept,
  }
}
