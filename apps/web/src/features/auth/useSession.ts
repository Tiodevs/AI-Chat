import { pt } from "@/i18n/pt.ts"
import { api } from "@/lib/api/client.ts"
import type { components } from "@/lib/api/schema.ts"

import { ApiRequestError, messageFrom, requestIdFrom } from "./api-error.ts"

export type Me = components["schemas"]["ProfileResponse"]

export const meQuery = {
  queryKey: ["me"] as const,
  queryFn: loadMe,
}

export async function loadMe(): Promise<Me | null> {
  const result = await api.GET("/v1/me")
  if (result.response.status === 401) {
    return null
  }
  if (!result.response.ok || !result.data) {
    throw new ApiRequestError(
      messageFrom(result.error, pt.couldNotContinue),
      requestIdFrom(result.error),
      result.response.status,
    )
  }
  return result.data
}
