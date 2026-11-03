import { useQuery } from "@tanstack/react-query"

import { AccountScreen } from "@/features/account/account-screen.tsx"
import { useAccount } from "@/features/account/useAccount.ts"
import { meQuery, type Me } from "@/features/auth/useSession.ts"

function AccountPage({ me }: { me: Me }) {
  const model = useAccount(me)
  return <AccountScreen {...model} />
}

export function Component() {
  const me = useQuery(meQuery).data
  if (!me) {
    return null
  }
  return <AccountPage me={me} />
}
