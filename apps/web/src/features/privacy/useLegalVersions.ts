import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client.ts"

export const legalVersionsQuery = {
  queryKey: ["legal", "versions"] as const,
  queryFn: async () => {
    const result = await api.GET("/v1/legal/versions")
    return result.data ?? null
  },
}

export function useLegalVersions() {
  const versions = useQuery(legalVersionsQuery).data
  return {
    version: versions?.privacy_notice ?? null,
    terms: versions?.terms ?? null,
    contactEmail: versions?.privacy_contact_email ?? null,
  }
}
