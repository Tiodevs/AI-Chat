import { TermsScreen } from "@/features/privacy/terms-screen.tsx"
import { useLegalVersions } from "@/features/privacy/useLegalVersions.ts"

export function Component() {
  const { terms } = useLegalVersions()
  return <TermsScreen version={terms} />
}
