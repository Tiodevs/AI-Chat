import { HomeScreen } from "@/features/ask/home-screen.tsx"
import { useAskConversation } from "@/features/ask/useAskConversation.ts"

export function Component() {
  const ask = useAskConversation(undefined)
  return (
    <HomeScreen
      pending={ask.pending}
      error={ask.error}
      budgetExceeded={ask.budgetExceeded}
      onAsk={ask.ask}
    />
  )
}
