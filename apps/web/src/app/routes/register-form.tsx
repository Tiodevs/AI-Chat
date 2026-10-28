import { RegistrationFormScreen } from "@/features/registration/registration-form-screen.tsx"
import { useRegistrationForm } from "@/features/registration/useRegistrationForm.ts"

export function Component() {
  const form = useRegistrationForm()
  return <RegistrationFormScreen {...form} />
}
