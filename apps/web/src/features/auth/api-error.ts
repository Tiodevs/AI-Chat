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

export function requestIdFrom(error: unknown): string | null {
  const body = errorBody(error)
  return typeof body?.request_id === "string" ? body.request_id : null
}

export function retryAfterFrom(error: unknown): number | null {
  const body = errorBody(error)
  return typeof body?.retry_after_seconds === "number" ? body.retry_after_seconds : null
}

export function messageFrom(error: unknown, fallback: string): string {
  const body = errorBody(error)
  return typeof body?.message === "string" ? body.message : fallback
}

function errorBody(error: unknown): { message?: unknown; request_id?: unknown; retry_after_seconds?: unknown } | null {
  if (!error || typeof error !== "object" || !("error" in error)) {
    return null
  }
  const body = error.error
  if (!body || typeof body !== "object") {
    return null
  }
  return body
}
