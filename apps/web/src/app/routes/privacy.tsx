import { PrivacyScreen } from "@/features/privacy/privacy-screen.tsx"
import { useLegalVersions } from "@/features/privacy/useLegalVersions.ts"
import { usePrivacyRequest } from "@/features/privacy/usePrivacyRequest.ts"

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
