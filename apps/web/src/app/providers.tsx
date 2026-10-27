import type { ReactNode } from "react"
import { QueryClientProvider } from "@tanstack/react-query"

import { queryClient } from "@/app/query-client.ts"
import { TooltipProvider } from "@/components/ui/tooltip.tsx"
import { MotionProvider } from "@/motion/MotionProvider.tsx"

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MotionProvider>
        <TooltipProvider>{children}</TooltipProvider>
      </MotionProvider>
    </QueryClientProvider>
  )
}
