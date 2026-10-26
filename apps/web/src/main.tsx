import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { RouterProvider } from "react-router"

import { AppProviders } from "@/app/providers.tsx"
import { router } from "@/app/router.tsx"
import "@/styles/globals.css"

const root = document.getElementById("root")
if (!root) {
  throw new Error("Elemento #root ausente")
}

createRoot(root).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
