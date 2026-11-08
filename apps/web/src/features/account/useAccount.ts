/**
 * Controlador da página da conta (`/account`). Lê os consentimentos e as
 * conversas do membro e executa as ações do titular: corrigir o perfil,
 * ligar e desligar consentimentos, exportar os dados e excluir a conta.
 *
 * Camada: controller (SDD 13.2). Quem usa: `app/routes/account.tsx`, que
 * passa o `me` já carregado pela guarda e entrega o retorno a
 * `AccountScreen`. Usa o cliente `api` (`lib/api/client.ts`), o
 * `queryClient` de `app/query-client.ts`, o `meQuery` de
 * `features/auth/useSession.ts` e as regras de `model.ts`.
 *
 * SDD 11.5 (direitos do titular), 11.6 (`DELETE /v1/me`), 12 (rotas
 * `/v1/me` e `/v1/conversations`) e 15.5 (Conta).
 */
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { meQuery, type Me } from "@/features/auth/useSession.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import {
  failureFrom,
  isGranted,
  personalizationPurpose,
  profilePatch,
  type Consents,
  type OptionalPurpose,
  type ProfileValues,
  type SubmitFailure,
} from "./model.ts"

/**
 * Consulta dos consentimentos, `GET /v1/me/consents`. A chave fica sob
 * `["me"]`, a chave do perfil: invalidar o perfil relê esta lista também.
 */
export const consentsQuery = {
  queryKey: ["me", "consents"] as const,
  queryFn: loadConsents,
}

/**
 * Consulta das conversas do membro, `GET /v1/conversations`, da mais
 * recente para a mais antiga. Também fica sob a chave `["me"]`.
 */
export const conversationsQuery = {
  queryKey: ["me", "conversations"] as const,
  queryFn: loadConversations,
}

// As duas leituras lançam um erro quando a API recusa: o `useQuery` marca
// `isError` e a aba mostra `pt.account.loadError`. Um 401 de sessão revogada
// também cai aqui, em vez de levar ao login como pede a seção 13.3. A
// Etapa 14.1 cria o 401 global que limpa o `me` e leva a `/sign-in`.
async function loadConsents(): Promise<Consents> {
  const result = await api.GET("/v1/me/consents")
  if (!result.response.ok || !result.data) {
    throw new Error(failureFrom(result.error, result.response.status).message)
  }
  return result.data
}

async function loadConversations() {
  const result = await api.GET("/v1/conversations")
  if (!result.response.ok || !result.data) {
    throw new Error(failureFrom(result.error, result.response.status).message)
  }
  return result.data.conversations
}

/**
 * Falha sem resposta HTTP, como a rede fora do ar: status 0, a cópia
 * genérica e nenhum `request_id` para copiar.
 */
function networkFailure(): SubmitFailure {
  return {
    ok: false,
    status: 0,
    message: pt.couldNotContinue,
    fieldErrors: {},
    requestId: null,
  }
}

/**
 * Salva um `Blob` como arquivo. Cria uma URL temporária para ele, clica num
 * link com `download` que só existe durante o clique e libera a URL.
 * Efeito colateral: o navegador baixa o arquivo com o nome dado.
 */
function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/**
 * Junta os dados e as ações da página da conta.
 *
 * As consultas de consentimentos e de conversas começam ao montar a página,
 * qualquer que seja a aba aberta. Cada ação devolve `null` no sucesso ou um
 * `SubmitFailure` para a tela mostrar, e nunca lança: um erro de rede vira
 * a cópia genérica.
 *
 * @param me Perfil do membro, já no cache pela guarda `requireUser`.
 * @returns O `AccountModel`: `me`, as consultas `consents` e
 *   `conversations`, a finalidade em mudança e as quatro ações.
 */
export function useAccount(me: Me) {
  const navigate = useNavigate()
  const consents = useQuery(consentsQuery)
  const conversations = useQuery(conversationsQuery)
  // A finalidade com pedido em curso. A tela trava só esse interruptor.
  const [changingPurpose, setChangingPurpose] = useState<string | null>(null)

  /**
   * Corrige o perfil com `PATCH /v1/me` (SDD 12). No sucesso, grava o
   * perfil devolvido no cache de `["me"]`: a casca e o formulário passam a
   * mostrar os dados novos sem outro pedido.
   */
  async function saveProfile(
    values: ProfileValues,
  ): Promise<SubmitFailure | null> {
    try {
      // Os campos sensíveis só seguem com a personalização vigente. Com os
      // consentimentos ainda carregando, `isGranted` dá falso e eles ficam
      // de fora.
      const body = profilePatch(
        values,
        isGranted(consents.data, personalizationPurpose),
      )
      const result = await api.PATCH("/v1/me", { body })
      if (!result.response.ok || !result.data) {
        return failureFrom(result.error, result.response.status)
      }
      queryClient.setQueryData(meQuery.queryKey, result.data)
      return null
    } catch {
      return networkFailure()
    }
  }

  /**
   * Liga ou desliga um consentimento opcional com
   * `PUT /v1/me/consents/{purpose}` (SDD 11.5 e 12). Cada mudança grava
   * `consent.change` na auditoria do servidor.
   *
   * 1. Marca a finalidade em mudança, para a tela travar o interruptor.
   * 2. Envia `{ granted }`. A resposta traz a lista nova de consentimentos,
   *    que vai direto para o cache: o interruptor só muda quando o
   *    servidor confirma.
   * 3. Na personalização, invalida o perfil. Revogar apaga `visitor_type` e
   *    `visit_reason` no servidor, na mesma transação, e o `me` precisa ser
   *    relido.
   * 4. Libera o interruptor, com sucesso ou com falha.
   */
  async function setConsent(
    purpose: OptionalPurpose,
    granted: boolean,
  ): Promise<SubmitFailure | null> {
    // 1.
    setChangingPurpose(purpose)
    try {
      // 2.
      const result = await api.PUT("/v1/me/consents/{purpose}", {
        params: { path: { purpose } },
        body: { granted },
      })
      if (!result.response.ok || !result.data) {
        return failureFrom(result.error, result.response.status)
      }
      queryClient.setQueryData(consentsQuery.queryKey, result.data)
      // 3. `["me"]` é prefixo das chaves da conta, então o
      // `invalidateQueries` relê o perfil, os consentimentos e as conversas.
      // O `await` espera essas leituras, e o interruptor segue travado.
      if (purpose === personalizationPurpose) {
        await queryClient.invalidateQueries({ queryKey: meQuery.queryKey })
      }
      return null
    } catch {
      return networkFailure()
    } finally {
      // 4.
      setChangingPurpose(null)
    }
  }

  /**
   * Baixa a exportação do titular, `GET /v1/me/export` (SDD 11.5 e 12):
   * perfil, consentimentos com versões, conversas com citações e feedback.
   *
   * `parseAs: "blob"` pede ao `openapi-fetch` o corpo cru, sem
   * `JSON.parse`. Como o download sai de uma URL de `Blob`, quem decide o
   * nome é o atributo `download`, igual ao `EXPORT_FILENAME` da API.
   */
  async function exportData(): Promise<SubmitFailure | null> {
    try {
      const result = await api.GET("/v1/me/export", { parseAs: "blob" })
      if (!result.response.ok || !result.data) {
        return failureFrom(result.error, result.response.status)
      }
      saveFile(result.data, "atrium-meus-dados.json")
      return null
    } catch {
      return networkFailure()
    }
  }

  /**
   * Exclui a conta com `DELETE /v1/me` (SDD 11.6 e 12). A API apaga os
   * dados do membro numa transação, responde 204 e apaga o cookie
   * `atrium_session`. Um admin recebe 403, e a tela mostra a recusa.
   *
   * 1. Esvazia o cache do TanStack Query: nenhum dado do membro fica na
   *    memória da aba.
   * 2. Grava `null` no perfil, para a casca virar a de visitante sem pedir
   *    `GET /v1/me` de novo. A ordem importa: o `clear` apagaria esse
   *    valor.
   * 3. Navega para o início.
   */
  async function deleteAccount(): Promise<SubmitFailure | null> {
    try {
      const result = await api.DELETE("/v1/me")
      // O 204 não tem corpo: só o status diz se deu certo.
      if (!result.response.ok) {
        return failureFrom(result.error, result.response.status)
      }
      // 1.
      queryClient.clear()
      // 2.
      queryClient.setQueryData(meQuery.queryKey, null)
      // 3.
      await navigate("/")
      return null
    } catch {
      return networkFailure()
    }
  }

  return {
    me,
    consents,
    conversations,
    changingPurpose,
    saveProfile,
    setConsent,
    exportData,
    deleteAccount,
  }
}

/** O que `AccountScreen` recebe: o retorno de `useAccount`. */
export type AccountModel = ReturnType<typeof useAccount>
