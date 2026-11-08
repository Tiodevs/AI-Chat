/**
 * Rota `/terms`, os Termos de Uso (seção 11.11).
 *
 * Liga o controller `useLegalVersions`, que lê `GET /v1/legal/versions`, à
 * tela `TermsScreen`, que mostra a versão vigente no topo. Pública: não tem
 * guard.
 */
import { TermsScreen } from "@/features/privacy/terms-screen.tsx"
import { useLegalVersions } from "@/features/privacy/useLegalVersions.ts"

/** Passa à tela só a versão dos Termos. */
export function Component() {
  const { terms } = useLegalVersions()
  return <TermsScreen version={terms} />
}
