import { RegistrationScreen } from "@/features/registration/registration-screen.tsx"
import { useRegistrationChat } from "@/features/registration/useRegistrationChat.ts"

export function Component() {
  const chat = useRegistrationChat()
  return <RegistrationScreen {...chat} />
}
