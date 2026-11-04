import { useQuery } from "@tanstack/react-query"

import { LegalAcceptScreen } from "@/features/account/legal-accept-screen.tsx"
import { useLegalAccept } from "@/features/account/useLegalAccept.ts"
import { meQuery, type Me } from "@/features/auth/useSession.ts"

function LegalAcceptPage({ me }: { me: Me }) {
  const model = useLegalAccept(me)
  return <LegalAcceptScreen {...model} />
}

export function Component() {
  const me = useQuery(meQuery).data
  if (!me) {
    return null
  }
  return <LegalAcceptPage me={me} />
}
