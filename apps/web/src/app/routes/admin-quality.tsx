import { QualityScreen } from "@/features/admin/quality-screen.tsx"
import { useQuality } from "@/features/admin/useInsights.ts"

export function Component() {
  const model = useQuality()
  return <QualityScreen {...model} />
}
