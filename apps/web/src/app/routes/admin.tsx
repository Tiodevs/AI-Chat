import { OverviewScreen } from "@/features/admin/overview-screen.tsx"
import { useOverview } from "@/features/admin/useInsights.ts"

export function Component() {
  const model = useOverview()
  return <OverviewScreen {...model} />
}
