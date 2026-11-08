/**
 * Rota `/register/form`, o cadastro por formulário: os mesmos campos,
 * aceites e regras do cadastro por conversa, numa página só (seções 7.2 e
 * 15.5).
 *
 * Liga o controller `useRegistrationForm` à tela `RegistrationFormScreen`
 * (SDD 13.2). Aberto a partir do chat, o formulário vem com os campos que a
 * IA já entendeu (FR-6).
 */
import { RegistrationFormScreen } from "@/features/registration/registration-form-screen.tsx"
import { useRegistrationForm } from "@/features/registration/useRegistrationForm.ts"

/** Passa o modelo do controller inteiro para a tela. */
export function Component() {
  const form = useRegistrationForm()
  return <RegistrationFormScreen {...form} />
}
