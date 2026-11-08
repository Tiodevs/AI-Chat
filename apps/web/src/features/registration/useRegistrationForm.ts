/**
 * Controlador do cadastro por formulário (`/register/form`). Seções 7.2, 12
 * e 15.5 do SDD.
 *
 * Lê a versão vigente dos documentos e, com `?session=` na URL, os campos
 * já entendidos no chat, para preencher o formulário (jornada J4, seção
 * 15.3). Envia tudo num pedido só, que a API conclui com a mesma função do
 * chat. O formulário não chama o modelo nem consulta o orçamento (seção
 * 7.2).
 *
 * Usado por `app/routes/register-form.tsx`, que passa o retorno inteiro
 * para a `RegistrationFormScreen`. Usa o cliente tipado
 * (`lib/api/client.ts`), o cache do TanStack Query (`meQuery`) e o
 * `sessionStorage`.
 */
import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { meQuery } from "@/features/auth/useSession.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"

import {
  emptyFormValues,
  failureFrom,
  formValuesFromFields,
  sessionIdFrom,
  toFormPayload,
  unavailableFrom,
  type FormValues,
  type SubmitFailure,
} from "./model.ts"

/**
 * A mesma chave de `useRegistrationChat.ts`: concluir pelo formulário apaga
 * o id do chat guardado na aba.
 */
const SESSION_KEY = "atrium.registration-session"

/**
 * Hook do formulário de cadastro.
 *
 * Devolve `loading`, os valores iniciais (`defaults`), a versão dos
 * documentos, o erro de carga com o `request_id`, a marca `unavailable` da
 * URL, o id da sessão do chat e `submit`.
 */
export function useRegistrationForm() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const sessionId = sessionIdFrom(params.get("session"))
  const unavailable = unavailableFrom(params.get("unavailable"))
  const [loading, setLoading] = useState(true)
  const [defaults, setDefaults] = useState(emptyFormValues)
  const [documentVersion, setDocumentVersion] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [requestId, setRequestId] = useState<string | null>(null)

  // Lê a versão e a sessão em paralelo. Como no chat, o `AbortController`
  // cancela os pedidos se a tela desmontar, e `signal.aborted` descarta as
  // respostas de um efeito já encerrado.
  useEffect(() => {
    const controller = new AbortController()
    const signal = controller.signal

    async function load() {
      try {
        const legalRequest = api.GET("/v1/legal/versions", { signal })
        const sessionRequest = sessionId
          ? api.GET("/v1/registration/sessions/{session_id}", {
              signal,
              params: { path: { session_id: sessionId } },
            })
          : null
        // O `Promise.all` aceita o `null` e o devolve como está.
        const [legal, existing] = await Promise.all([
          legalRequest,
          sessionRequest,
        ])
        if (signal.aborted) {
          return
        }
        // Sem a versão, o botão de envio fica desabilitado, e a tela mostra
        // o erro com o `request_id`.
        if (legal.data?.terms) {
          setDocumentVersion(legal.data.terms)
        } else {
          const failure = failureFrom(legal.error, legal.response.status)
          setLoadError(failure.message)
          setRequestId(failure.requestId)
        }
        // Sem `?session=`, o formulário começa vazio.
        if (!existing) {
          return
        }
        if (existing.data) {
          setDefaults(formValuesFromFields(existing.data.fields))
          return
        }
        // A sessão não existe mais: a pessoa preenche do zero.
        if (existing.response.status === 404) {
          setLoadError(pt.registration.sessionMissing)
          return
        }
        const failure = failureFrom(existing.error, existing.response.status)
        setLoadError(failure.message)
        setRequestId(failure.requestId)
      } catch {
        if (!signal.aborted) {
          setLoadError(pt.couldNotContinue)
        }
      } finally {
        if (!signal.aborted) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [sessionId])

  /**
   * Envia o formulário completo (`POST /v1/registration/form`).
   *
   * Devolve `null` no sucesso, depois de apagar o id do chat guardado, pôr
   * o perfil devolvido no cache do `meQuery` e navegar para `/account`. A
   * API cria a conta e define o cookie `atrium_session`. Numa falha,
   * devolve a `SubmitFailure`, e a tela põe os erros nos campos. O e-mail
   * já cadastrado responde 409 (seção 12).
   */
  async function submit(values: FormValues): Promise<SubmitFailure | null> {
    // A tela já desabilita o envio sem a versão; o hook repete a proteção.
    if (!documentVersion) {
      return {
        ok: false,
        status: 0,
        message: pt.couldNotContinue,
        fieldErrors: {},
        requestId: null,
      }
    }
    try {
      const result = await api.POST("/v1/registration/form", {
        body: toFormPayload(values, documentVersion, sessionId),
      })
      if (!result.response.ok || !result.data) {
        return failureFrom(result.error, result.response.status)
      }
      sessionStorage.removeItem(SESSION_KEY)
      queryClient.setQueryData(meQuery.queryKey, result.data)
      await navigate("/account")
      return null
    } catch {
      return {
        ok: false,
        status: 0,
        message: pt.couldNotContinue,
        fieldErrors: {},
        requestId: null,
      }
    }
  }

  return {
    loading,
    defaults,
    documentVersion,
    loadError,
    requestId,
    unavailable,
    sessionId,
    submit,
  }
}
