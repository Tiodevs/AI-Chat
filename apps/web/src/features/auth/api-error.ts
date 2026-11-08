/**
 * Leitura do envelope de erro da API e o erro que as rotas mostram. Seção
 * 12 do SDD (forma única dos erros) e seção 13.3 (error boundary com o
 * `request_id`).
 *
 * Numa resposta de erro, o `openapi-fetch` põe o corpo em `error`: o JSON
 * `{ error: { code, message, request_id, ... } }` ou, se o corpo não for
 * JSON, o texto. As funções daqui leem esse valor sem confiar no formato e
 * caem no padrão quando um campo falta.
 *
 * Usado por `useSession.ts` e `useSignIn.ts`, pelos hooks de
 * `features/ask`, `features/privacy` e `features/admin`, por
 * `features/registration/model.ts` e por `app/route-frame.tsx`.
 */

/**
 * Erro de uma leitura da API, com o `request_id` e o status HTTP. `loadMe`
 * o lança, e o error boundary de `app/route-frame.tsx` mostra a mensagem e
 * o `request_id` copiável (seção 13.3).
 */
export class ApiRequestError extends Error {
  readonly requestId: string | null
  readonly status: number

  constructor(message: string, requestId: string | null, status: number) {
    super(message)
    this.name = "ApiRequestError"
    this.requestId = requestId
    this.status = status
  }
}

/** `request_id` do envelope, ou `null`. */
export function requestIdFrom(error: unknown): string | null {
  const body = errorBody(error)
  return typeof body?.request_id === "string" ? body.request_id : null
}

/**
 * Segundos de espera de um 429 (`retry_after_seconds`, seção 10.4), ou
 * `null`.
 */
export function retryAfterFrom(error: unknown): number | null {
  const body = errorBody(error)
  return typeof body?.retry_after_seconds === "number"
    ? body.retry_after_seconds
    : null
}

/** Mensagem em português do envelope, ou `fallback` quando ela falta. */
export function messageFrom(error: unknown, fallback: string): string {
  const body = errorBody(error)
  return typeof body?.message === "string" ? body.message : fallback
}

/**
 * Erros por campo (`field_errors`), só com as mensagens que são texto.
 * Objeto vazio quando não há.
 */
export function fieldErrorsFrom(error: unknown): Record<string, string> {
  const body = errorBody(error)
  const source = body?.field_errors
  if (!source || typeof source !== "object") {
    return {}
  }
  const errors: Record<string, string> = {}
  for (const [field, message] of Object.entries(source)) {
    if (typeof message === "string") {
      errors[field] = message
    }
  }
  return errors
}

/**
 * O objeto `error` de dentro do envelope, ou `null` se o valor não tem essa
 * forma, como o texto de uma página de erro.
 */
function errorBody(error: unknown): {
  message?: unknown
  request_id?: unknown
  retry_after_seconds?: unknown
  field_errors?: unknown
} | null {
  if (!error || typeof error !== "object" || !("error" in error)) {
    return null
  }
  const body = error.error
  if (!body || typeof body !== "object") {
    return null
  }
  return body
}
