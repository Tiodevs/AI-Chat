import { PrivacyQueueScreen } from "@/features/admin/privacy-queue-screen.tsx"
import { usePrivacyQueue } from "@/features/admin/usePrivacyQueue.ts"

export function Component() {
  const model = usePrivacyQueue()
  return <PrivacyQueueScreen {...model} />
}
