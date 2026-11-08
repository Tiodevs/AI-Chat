/**
 * Rota `/register`, o cadastro por conversa com a IA (seções 7.2 e 15.5).
 *
 * Liga o controller `useRegistrationChat` à tela `RegistrationScreen` (SDD
 * 13.2): o chat, o resumo do que a IA entendeu, a senha fora do chat e os
 * aceites.
 */
import { RegistrationScreen } from "@/features/registration/registration-screen.tsx"
import { useRegistrationChat } from "@/features/registration/useRegistrationChat.ts"

/** Passa o modelo do controller inteiro para a tela. */
export function Component() {
  const chat = useRegistrationChat()
  return <RegistrationScreen {...chat} />
}
