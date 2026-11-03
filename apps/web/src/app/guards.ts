import { redirect, type LoaderFunctionArgs } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { meQuery } from "@/features/auth/useSession.ts"

function returnToOf(request: Request) {
  const url = new URL(request.url)
  return encodeURIComponent(`${url.pathname}${url.search}`)
}

/** Exige sessão, sem olhar o aceite. Serve à tela do novo aceite. */
export async function requireSession({ request }: LoaderFunctionArgs) {
  const me = await queryClient.ensureQueryData(meQuery)
  if (!me) {
    throw redirect(`/sign-in?returnTo=${returnToOf(request)}`)
  }
  return me
}

/** Exige sessão e o aceite da versão vigente dos documentos legais. SDD 13.3. */
export async function requireUser(args: LoaderFunctionArgs) {
  const me = await requireSession(args)
  if (me.needs_legal_acceptance) {
    throw redirect(`/legal/accept?returnTo=${returnToOf(args.request)}`)
  }
  return me
}

export async function requireAdmin(args: LoaderFunctionArgs) {
  const me = await requireUser(args)
  if (me.role !== "admin") {
    throw new Response(null, { status: 403 })
  }
  return me
}
