/**
 * Leitura da versão vigente dos Termos e do Aviso de Privacidade e do
 * contato do encarregado, em `GET /v1/legal/versions`.
 *
 * Camada: controller (SDD 13.2). Quem usa: as rotas `app/routes/privacy.tsx`
 * e `app/routes/terms.tsx`, pelo `useLegalVersions`, e o
 * `features/account/useLegalAccept.ts`, pela `legalVersionsQuery`. As três
 * telas dividem a mesma entrada do cache. Usa o cliente `api`.
 *
 * SDD 11.11 (versão dos documentos) e 12.
 */
import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client.ts"

/**
 * Consulta de `GET /v1/legal/versions`. Uma falha não lança: a consulta
 * devolve `null`, e as telas seguem sem a versão e sem o contato.
 */
export const legalVersionsQuery = {
  queryKey: ["legal", "versions"] as const,
  queryFn: async () => {
    const result = await api.GET("/v1/legal/versions")
    return result.data ?? null
  },
}

/**
 * Versões e contato prontos para as telas, com `null` enquanto carregam ou
 * quando a leitura falha.
 *
 * @returns `version`, a versão do Aviso; `terms`, a dos Termos; e
 *   `contactEmail`, o e-mail do encarregado, nulo quando
 *   `PRIVACY_CONTACT_EMAIL` está vazia na API (SDD 12).
 */
export function useLegalVersions() {
  const versions = useQuery(legalVersionsQuery).data
  return {
    version: versions?.privacy_notice ?? null,
    terms: versions?.terms ?? null,
    contactEmail: versions?.privacy_contact_email ?? null,
  }
}
