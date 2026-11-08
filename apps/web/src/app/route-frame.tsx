/**
 * A moldura das páginas: uma rota sem `path` entre a casca e as páginas,
 * com o `ErrorBoundary` que todas dividem (seção 13.3).
 *
 * No React Router, um erro lançado por um `loader`, pelo `lazy` ou na
 * renderização de uma página sobe até o `ErrorBoundary` mais próximo.
 * Como esta moldura fica dentro da casca, a tela de erro aparece com a
 * barra lateral ou o cabeçalho no lugar, e a pessoa ainda navega.
 *
 * Quem usa: `router.tsx`, por `lazy`. O arquivo vai como `modulepreload`
 * no `index.html` (`vite.config.ts`). Usa o `PageHeading`, o
 * `RequestIdCopy` e o `ApiRequestError` de `features/auth/api-error.ts`.
 */
import { isRouteErrorResponse, Link, Outlet, useRouteError } from "react-router"

import { PageHeading } from "@/app/page-heading.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { Button } from "@/components/ui/button.tsx"
import { ApiRequestError } from "@/features/auth/api-error.ts"
import { pt } from "@/i18n/pt.ts"

/** Só repassa a página filha, pelo `Outlet`. */
export function Component() {
  return <Outlet />
}

/**
 * A tela de erro de qualquer página.
 *
 * 1. Um 403, que `requireAdmin` lança, mostra "Acesso negado" e o link
 *    para o início.
 * 2. Um `ApiRequestError`, como a falha de `GET /v1/me` num guard, mostra a
 *    mensagem da API e o `request_id` copiável.
 * 3. Qualquer outro erro mostra a cópia genérica, sem `request_id`. Entra
 *    aqui o módulo de rota que não baixa numa aba aberta antes de um
 *    deploy; a Etapa 14.1 recarrega a página nesse caso.
 */
export function ErrorBoundary() {
  const error = useRouteError()
  // 1. `isRouteErrorResponse` reconhece a `Response` lançada por um
  // `loader`.
  if (isRouteErrorResponse(error) && error.status === 403) {
    return (
      <div className="flex max-w-xl flex-col gap-4">
        <PageHeading title={pt.forbidden.title} />
        <p className="text-body text-foreground">{pt.forbidden.body}</p>
        {/* 44 px de altura no celular e 32 px a partir de `md`: os alvos
            de toque da seção 15.8. */}
        <Button asChild variant="link" className="h-11 w-fit px-0 md:h-8">
          <Link to="/">{pt.forbidden.home}</Link>
        </Button>
      </div>
    )
  }

  // 2. e 3. Só o `ApiRequestError` traz o `request_id` do pedido que falhou.
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
