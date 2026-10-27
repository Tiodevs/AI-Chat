import { isRouteErrorResponse, Link, Outlet, useRouteError } from "react-router"

import { PageHeading } from "@/app/page-heading.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { Button } from "@/components/ui/button.tsx"
import { ApiRequestError } from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"

export function Component() {
  return <Outlet />
}

export function ErrorBoundary() {
  const error = useRouteError()
  if (isRouteErrorResponse(error) && error.status === 403) {
    return (
      <div className="flex max-w-xl flex-col gap-4">
        <PageHeading title={pt.forbidden.title} />
        <p className="text-body text-foreground">{pt.forbidden.body}</p>
        <Button asChild variant="link" className="h-11 w-fit px-0 md:h-8">
          <Link to="/">{pt.forbidden.home}</Link>
        </Button>
      </div>
    )
  }

  const requestId = error instanceof ApiRequestError ? error.requestId : null
  const message = error instanceof ApiRequestError ? error.message : pt.error.body
  return (
    <div className="flex max-w-xl flex-col gap-4">
      <PageHeading title={pt.couldNotContinue} />
      <p className="text-body text-foreground">{message}</p>
      {requestId ? <RequestIdCopy requestId={requestId} /> : null}
    </div>
  )
}
