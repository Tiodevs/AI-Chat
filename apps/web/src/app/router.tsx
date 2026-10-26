import { createBrowserRouter, type RouteObject } from "react-router"

import { pt } from "@/i18n/pt.ts"

function ShellFallback() {
  return <p className="p-6 text-body text-muted-foreground">{pt.loading}</p>
}

export const routes: RouteObject[] = [
  {
    path: "/",
    HydrateFallback: ShellFallback,
    lazy: () => import("./shell.tsx"),
    children: [
      { index: true, lazy: () => import("./routes/home.tsx") },
      { path: "ask/:id?", lazy: () => import("./routes/ask.tsx") },
      { path: "register", lazy: () => import("./routes/register.tsx") },
      {
        path: "register/form",
        lazy: () => import("./routes/register-form.tsx"),
      },
      { path: "sign-in", lazy: () => import("./routes/sign-in.tsx") },
      { path: "account", lazy: () => import("./routes/account.tsx") },
      { path: "privacy", lazy: () => import("./routes/privacy.tsx") },
      { path: "terms", lazy: () => import("./routes/terms.tsx") },
      { path: "legal/accept", lazy: () => import("./routes/legal-accept.tsx") },
      { path: "admin", lazy: () => import("./routes/admin.tsx") },
      {
        path: "admin/documents",
        lazy: () => import("./routes/admin-documents.tsx"),
      },
      {
        path: "admin/quality",
        lazy: () => import("./routes/admin-quality.tsx"),
      },
      {
        path: "admin/privacy",
        lazy: () => import("./routes/admin-privacy.tsx"),
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
