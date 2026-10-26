import type { ReactNode } from "react"

import { TooltipProvider } from "@/components/ui/tooltip.tsx"
import { MotionProvider } from "@/motion/MotionProvider.tsx"

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <MotionProvider>
      <TooltipProvider>{children}</TooltipProvider>
    </MotionProvider>
  )
}
