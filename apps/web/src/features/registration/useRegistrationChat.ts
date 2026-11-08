/**
 * Controlador do cadastro por conversa (`/register`). Seções 7.2, 12 e 15.5
 * do SDD.
 *
 * Abre ou retoma a sessão de cadastro e envia cada passo: os turnos do
 * chat, a edição do cartão, a senha, a revisão e os aceites. A máquina de
 * estados fica na API (seção 7.2): o hook manda o pedido do passo, guarda a
 * sessão que volta e transforma as falhas no aviso que a conversa mostra.
 *
 * Usado por `app/routes/register.tsx`, que passa o retorno inteiro para a
 * `RegistrationScreen`. Usa o cliente tipado (`lib/api/client.ts`), o
 * cache do TanStack Query (`meQuery`) e o `sessionStorage`.
 */
import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { meQuery } from "@/features/auth/useSession.ts"
import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"
import type { components } from "@/lib/api/schema.ts"

import {
  failureFrom,
  sessionIdFrom,
  type Consents,
  type FieldName,
  type RegistrationSession,
} from "./model.ts"

/**
 * Chave do `sessionStorage` com o id da sessão de cadastro. Uma recarga na
 * mesma aba retoma o cadastro, e a conclusão apaga a chave. Na API, a
 * sessão expira em 24 horas (seção 10.3).
 */
const SESSION_KEY = "atrium.registration-session"

/** Sessão como o OpenAPI a descreve (`schema.ts`, seção 6.6). */
type SessionResponse = components["schemas"]["RegistrationSessionResponse"]

/** Copia a resposta da API no tipo da tela, campo a campo. */
function asSession(data: SessionResponse): RegistrationSession {
  return {
    id: data.id,
    status: data.status,
    path: data.path,
    fields: data.fields,
    field_errors: data.field_errors,
    next_step: data.next_step,
    prompt: data.prompt,
    messages: data.messages.map((message) => ({
      role: message.role,
      text: message.text,
      created_at: message.created_at,
    })),
    expires_at: data.expires_at,
  }
}

/** A sessão ainda aceita passos: não está concluída nem abandonada. */
function resumable(status: string) {
  return status !== "completed" && status !== "abandoned"
}

/**
 * Aviso de falha que a conversa mostra no `ChatErrorNotice`, sem sair da
 * tela (seção 15.5, Estados).
 */
export type ChatNotice = {
  /** Mensagem em português, da API ou genérica. */
  message: string
  /** `request_id` do envelope, para o `RequestIdCopy`. */
  requestId: string | null
  /** O provedor de IA está fora. A tela oferece o formulário. */
  unavailable: boolean
  /** Texto que falhou, para tentar de novo. */
  retryText: string | null
}

/**
 * Hook do cadastro por conversa.
 *
 * Ao montar, lê a versão vigente dos documentos legais e abre a sessão:
 * retoma a do `sessionStorage`, se ela ainda aceita passos, ou começa
 * outra. Cada ação devolve a sessão nova da API, guardada por `remember`.
 * Uma falha vira o `notice`, e a pessoa continua na tela.
 *
 * Devolve a sessão, os estados (`loading`, `pending`, `notice`, `outgoing`
 * e `actionErrors`) e as ações `send`, `skip`, `editField`, `setPassword`,
 * `review`, `accept` e `dismissNotice`.
 */
export function useRegistrationChat() {
  const navigate = useNavigate()
  const [session, setSession] = useState<RegistrationSession | null>(null)
  // Verdadeiro até a sessão abrir ou falhar.
  const [loading, setLoading] = useState(true)
  // Um pedido de passo em andamento. Bloqueia os outros.
  const [pending, setPending] = useState(false)
  const [notice, setNotice] = useState<ChatNotice | null>(null)
  // Mensagem a caminho. A tela já a mostra, com o assistente escrevendo
  // (seção 15.5).
  const [outgoing, setOutgoing] = useState<string | null>(null)
  // Versão vigente dos Termos, de `GET /v1/legal/versions`. O aceite a
  // envia (seção 7.2).
  const [documentVersion, setDocumentVersion] = useState<string | null>(null)
  // Erros por campo da resposta do aceite.
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({})

  /**
   * Transforma a resposta de erro no aviso da conversa. O 503 é o modelo
   * indisponível ou o orçamento estourado (seção 7.2): o aviso usa o texto
   * fixo e oferece o formulário. `retryText` liga o Tentar de novo.
   *
   * Fica em `useCallback` para manter a mesma referência entre renders,
   * porque entra nas dependências do efeito de abertura.
   */
  const fail = useCallback(
    (error: unknown, status: number, retryText: string | null = null) => {
      const failure = failureFrom(error, status)
      setNotice({
        message:
          status === 503 ? pt.registration.unavailable : failure.message,
        requestId: failure.requestId,
        unavailable: status === 503,
        retryText,
      })
    },
    []
  )

  /** Aviso de falha sem resposta da API, como a rede. Sem `request_id`. */
  const crash = useCallback((retryText: string | null = null) => {
    setNotice({
      message: pt.couldNotContinue,
      requestId: null,
      unavailable: false,
      retryText,
    })
  }, [])

  /**
   * Guarda a sessão que a API devolveu: o id no `sessionStorage`, para
   * retomar depois de recarregar, e a sessão no estado. Limpa os erros do
   * aceite.
   */
  const remember = useCallback((next: RegistrationSession) => {
    sessionStorage.setItem(SESSION_KEY, next.id)
    setSession(next)
    setActionErrors({})
  }, [])

  // Abre a sessão ao montar. O `AbortController` cancela os pedidos se a
  // tela desmontar antes da resposta, e cada `signal.aborted` impede que um
  // efeito encerrado mexa no estado. No `StrictMode` de desenvolvimento, o
  // React monta, desmonta e monta de novo; o aborto só cancela a espera no
  // navegador, e a API pode já ter criado a primeira sessão.
  useEffect(() => {
    const controller = new AbortController()
    const signal = controller.signal

    /**
     * Abre a sessão e lê a versão dos documentos, em paralelo.
     *
     * 1. Sem id guardado: lê a versão e começa a sessão com
     *    `POST /v1/registration/sessions`, que já traz a saudação fixa.
     * 2. Com id guardado: lê a versão e a sessão, com
     *    `GET /v1/registration/sessions/{id}`.
     * 3. A sessão guardada que ainda aceita passos é retomada. Qualquer
     *    outro resultado, como 404, sessão concluída ou erro, começa outra.
     */
    async function load() {
      /** Guarda a sessão recém-criada ou mostra a falha. */
      async function openStarted(started: {
        response: { status: number; ok: boolean }
        data?: SessionResponse
        error?: unknown
      }) {
        if (!started.response.ok || !started.data) {
          fail(started.error, started.response.status)
          return
        }
        remember(asSession(started.data))
      }

      try {
        const stored = sessionIdFrom(sessionStorage.getItem(SESSION_KEY))
        const legalRequest = api.GET("/v1/legal/versions", { signal })
        // 1.
        if (!stored) {
          const [legal, started] = await Promise.all([
            legalRequest,
            api.POST("/v1/registration/sessions", { signal }),
          ])
          if (signal.aborted) {
            return
          }
          // Sem a versão, `accept` mostra o aviso genérico no fim.
          if (legal.data?.terms) {
            setDocumentVersion(legal.data.terms)
          }
          await openStarted(started)
          return
        }
        // 2.
        const [legal, existing] = await Promise.all([
          legalRequest,
          api.GET("/v1/registration/sessions/{session_id}", {
            signal,
            params: { path: { session_id: stored } },
          }),
        ])
        if (signal.aborted) {
          return
        }
        if (legal.data?.terms) {
          setDocumentVersion(legal.data.terms)
        }
        // 3.
        if (existing.data && resumable(existing.data.status)) {
          remember(asSession(existing.data))
          return
        }
        const started = await api.POST("/v1/registration/sessions", { signal })
        if (signal.aborted) {
          return
        }
        await openStarted(started)
      } catch {
        if (!signal.aborted) {
          crash()
        }
      } finally {
        if (!signal.aborted) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [crash, fail, remember])

  /**
   * Envia um turno do chat
   * (`POST /v1/registration/sessions/{id}/messages`). Seção 7.2 do SDD.
   *
   * Devolve `true` quando a API aceitou o turno, e só então a tela limpa o
   * campo. Numa falha, o aviso guarda o texto para o Tentar de novo, e o
   * campo continua com ele (seção 15.5). Enquanto espera, `outgoing` mostra
   * a mensagem na conversa.
   */
  async function send(text: string) {
    if (!session || pending || !text.trim()) {
      return false
    }
    const trimmed = text.trim()
    setPending(true)
    setNotice(null)
    setOutgoing(trimmed)
    try {
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/messages",
        {
          params: { path: { session_id: session.id } },
          body: { text: trimmed },
        }
      )
      if (!result.response.ok || !result.data) {
        fail(result.error, result.response.status, trimmed)
        return false
      }
      remember(asSession(result.data))
      return true
    } catch {
      crash(trimmed)
      return false
    } finally {
      setOutgoing(null)
      setPending(false)
    }
  }

  /**
   * Edita um campo no cartão de resumo
   * (`PATCH /v1/registration/sessions/{id}/fields`), com as regras do
   * formulário (seção 12). Envia só o campo editado; `null` limpa o campo.
   * Devolve `true` no sucesso, para o cartão fechar o editor.
   *
   * O `pending` impede editar e conversar ao mesmo tempo nesta aba. Entre
   * abas, a Etapa 13.3 acrescenta o 409 de versão, e o frontend passa a
   * recarregar a sessão.
   */
  async function editField(field: FieldName, value: string | null) {
    if (!session || pending) {
      return false
    }
    setPending(true)
    setNotice(null)
    try {
      // A chave calculada monta `{ email: "..." }`, por exemplo.
      const body: components["schemas"]["FieldsPatchRequest"] = {
        [field]: value,
      }
      const result = await api.PATCH(
        "/v1/registration/sessions/{session_id}/fields",
        {
          params: { path: { session_id: session.id } },
          body,
        }
      )
      if (!result.response.ok || !result.data) {
        fail(result.error, result.response.status)
        return false
      }
      remember(asSession(result.data))
      return true
    } catch {
      crash()
      return false
    } finally {
      setPending(false)
    }
  }

  /**
   * Envia a senha (`POST /v1/registration/sessions/{id}/password`), fora do
   * chat: ela não entra na transcrição nem vai ao modelo (seções 7.2 e
   * 15.6). A API grava só o hash e passa para a revisão. Uma senha fora da
   * regra volta em `field_errors.password`, e o passo continua o mesmo.
   */
  async function setPassword(password: string) {
    if (!session || pending) {
      return
    }
    setPending(true)
    setNotice(null)
    try {
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/password",
        {
          params: { path: { session_id: session.id } },
          body: { password },
        }
      )
      if (!result.response.ok || !result.data) {
        fail(result.error, result.response.status)
        return
      }
      remember(asSession(result.data))
    } catch {
      crash()
    } finally {
      setPending(false)
    }
  }

  /**
   * Responde à revisão (`POST /v1/registration/sessions/{id}/review`).
   * `true` confirma o resumo e leva ao aceite; `false` volta à conversa
   * para corrigir um campo (seção 15.5, Passo de revisão).
   */
  async function review(accept: boolean) {
    if (!session || pending) {
      return
    }
    setPending(true)
    setNotice(null)
    try {
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/review",
        {
          params: { path: { session_id: session.id } },
          body: { accept },
        }
      )
      if (!result.response.ok || !result.data) {
        fail(result.error, result.response.status)
        return
      }
      remember(asSession(result.data))
    } catch {
      crash()
    } finally {
      setPending(false)
    }
  }

  /**
   * Conclui o cadastro com os aceites
   * (`POST /v1/registration/sessions/{id}/acceptance`, seção 7.2).
   *
   * 1. Sem a versão vigente dos documentos, mostra o aviso genérico.
   * 2. Envia os quatro aceites e a versão. A API cria a conta, abre a
   *    sessão de autenticação e define o cookie `atrium_session`.
   * 3. Numa falha com erros por campo, eles vão para `actionErrors`; sem
   *    eles, o aviso da conversa mostra a mensagem. O `AcceptStep` mostra
   *    só os erros de `accept_terms` e `age_18_plus`.
   * 4. No sucesso, apaga o id guardado, põe o perfil devolvido no cache do
   *    `meQuery` e navega para `/account`. A guarda da conta acha o perfil
   *    no cache e não pede `GET /v1/me` de novo.
   */
  async function accept(consents: Consents) {
    if (!session || pending) {
      return
    }
    // 1.
    if (!documentVersion) {
      crash()
      return
    }
    setPending(true)
    setNotice(null)
    setActionErrors({})
    try {
      // 2.
      const result = await api.POST(
        "/v1/registration/sessions/{session_id}/acceptance",
        {
          params: { path: { session_id: session.id } },
          body: {
            accept_terms: consents.accept_terms,
            document_version: documentVersion,
            age_18_plus: consents.age_18_plus,
            profile_personalization: consents.profile_personalization,
            quality_improvement: consents.quality_improvement,
          },
        }
      )
      // 3.
      if (!result.response.ok || !result.data) {
        const failure = failureFrom(result.error, result.response.status)
        setActionErrors(failure.fieldErrors)
        if (Object.keys(failure.fieldErrors).length === 0) {
          fail(result.error, result.response.status)
        }
        return
      }
      // 4.
      sessionStorage.removeItem(SESSION_KEY)
      queryClient.setQueryData(meQuery.queryKey, result.data)
      await navigate("/account")
    } catch {
      crash()
    } finally {
      setPending(false)
    }
  }

  return {
    session,
    loading,
    pending,
    notice,
    outgoing,
    dismissNotice: () => setNotice(null),
    actionErrors,
    send,
    // Pular envia uma frase fixa como turno comum. A extração da API lê o
    // pedido e marca `skip_current` (seção 7.2).
    skip: () => send(pt.registration.skipMessage),
    editField,
    setPassword,
    review,
    accept,
  }
}
