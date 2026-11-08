/**
 * Rota `/privacy`: o Aviso de Privacidade e o formulário do canal do
 * titular (seções 11.11 e 15.5).
 *
 * Junta dois controllers para a tela `PrivacyScreen` (SDD 13.2):
 * `useLegalVersions`, com a versão vigente do Aviso e o contato do
 * encarregado, e `usePrivacyRequest`, com o envio do pedido e o e-mail de
 * quem entrou, para preencher o campo. Pública: não tem guard.
 */
import { PrivacyScreen } from "@/features/privacy/privacy-screen.tsx"
import { useLegalVersions } from "@/features/privacy/useLegalVersions.ts"
import { usePrivacyRequest } from "@/features/privacy/usePrivacyRequest.ts"

/** Passa à tela a versão, o contato e o envio do pedido. */
export function Component() {
  const { version, contactEmail } = useLegalVersions()
  const { email, submit } = usePrivacyRequest()
  return (
    <PrivacyScreen
      version={version}
      contactEmail={contactEmail}
      email={email}
      submit={submit}
    />
  )
}
