import { redirect, type LoaderFunctionArgs } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { meQuery } from "@/features/auth/useSession.ts"

export async function requireUser({ request }: LoaderFunctionArgs) {
  const me = await queryClient.ensureQueryData(meQuery)
  if (!me) {
    const url = new URL(request.url)
    const returnTo = `${url.pathname}${url.search}`
    throw redirect(`/sign-in?returnTo=${encodeURIComponent(returnTo)}`)
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
