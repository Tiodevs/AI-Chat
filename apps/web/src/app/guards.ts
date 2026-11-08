/**
 * Os guards das rotas protegidas, usados como `loader` em `router.tsx`.
 *
 * Um `loader` do React Router roda antes de a rota aparecer. Lançar um
 * `redirect` troca a navegação por outra URL; lançar uma `Response` ou um
 * erro leva ao `ErrorBoundary` mais próximo, o de `route-frame.tsx`.
 *
 * Os três leem o perfil, `GET /v1/me`, pelo `meQuery` de
 * `features/auth/useSession.ts`, no `queryClient` compartilhado: rodam fora
 * do React e não têm o `useQueryClient`. Cada um chama o anterior, então
 * as checagens somam. SDD 13.3.
 */
import { redirect, type LoaderFunctionArgs } from "react-router"

import { queryClient } from "@/app/query-client.ts"
import { meQuery } from "@/features/auth/useSession.ts"

/**
 * O caminho e a busca da URL pedida, codificados para irem no `returnTo`.
 * A codificação mantém a `?` e o `&` da busca original dentro do valor. Ao
 * entrar, `useSignIn` volta para lá, depois de o `safeReturnTo` de
 * `features/auth/return-to.ts` recusar o que não for caminho interno.
 */
function returnToOf(request: Request) {
  const url = new URL(request.url)
  return encodeURIComponent(`${url.pathname}${url.search}`)
}

/**
 * Exige sessão, sem olhar o aceite. Serve à tela do novo aceite.
 *
 * `ensureQueryData` devolve o `me` do cache quando ele existe e só chama a
 * API quando não existe. Por isso uma sessão revogada depois da primeira
 * leitura pode passar por aqui; a Etapa 14.1 cria o 401 global que limpa o
 * `me` e leva ao login. Uma falha da API que não seja 401 vira um
 * `ApiRequestError`, e a moldura mostra a mensagem com o `request_id`.
 *
 * @returns O perfil de quem entrou.
 * @throws `redirect` para `/sign-in?returnTo=...` quando não há sessão.
 */
export async function requireSession({ request }: LoaderFunctionArgs) {
  const me = await queryClient.ensureQueryData(meQuery)
  if (!me) {
    throw redirect(`/sign-in?returnTo=${returnToOf(request)}`)
  }
  return me
}

/**
 * Exige sessão e o aceite da versão vigente dos documentos legais.
 * SDD 13.3.
 *
 * @throws `redirect` para `/legal/accept?returnTo=...` quando há uma
 *   versão nova dos Termos ou do Aviso para aceitar.
 */
export async function requireUser(args: LoaderFunctionArgs) {
  const me = await requireSession(args)
  if (me.needs_legal_acceptance) {
    throw redirect(`/legal/accept?returnTo=${returnToOf(args.request)}`)
  }
  return me
}

/**
 * Exige sessão, aceite em dia e `role` admin. A ordem importa: um admin
 * com aceite pendente vai primeiro para `/legal/accept`, como no primeiro
 * login do admin (seção 22.1).
 *
 * @throws `Response` 403 para outro papel. O `ErrorBoundary` de
 *   `route-frame.tsx` mostra a página de acesso negado.
 */
export async function requireAdmin(args: LoaderFunctionArgs) {
  const me = await requireUser(args)
  if (me.role !== "admin") {
    throw new Response(null, { status: 403 })
  }
  return me
}
