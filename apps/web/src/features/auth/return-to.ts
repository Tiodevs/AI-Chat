/**
 * Destino depois de entrar e o texto do limite de login. Seções 10.4 e 13.3
 * do SDD.
 *
 * Usado por `useSignIn.ts` e por `features/account/useLegalAccept.ts`, que
 * leem o `returnTo` da URL. As guardas de `app/guards.ts` montam esse
 * `returnTo` com o caminho da rota protegida.
 */
import { pt } from "@/i18n/pt.ts"

/**
 * Aceita só um caminho da própria origem, para o `returnTo` da URL não
 * levar a pessoa a outro site depois de entrar (redirecionamento aberto).
 *
 * Recusa o que não começa com `/`, o `//` (outro host, sem protocolo), a
 * barra invertida, que o navegador lê como `/`, e qualquer `://`. Nesses
 * casos, e sem valor, devolve `/`. A Etapa 15.2 passa a validar com
 * `new URL`.
 */
export function safeReturnTo(value: string | null): string {
  if (
    value === null ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.startsWith("/\\") ||
    value.includes("\\") ||
    value.includes("://")
  ) {
    return "/"
  }
  return value
}

/**
 * Texto do limite de tentativas de login, em minutos, com mínimo de 1
 * (seção 10.4).
 */
export function limitMessage(retryAfterSeconds: number): string {
  const minutes = Math.max(1, Math.ceil(retryAfterSeconds / 60))
  if (minutes === 1) {
    return pt.signIn.limitedOne
  }
  return pt.signIn.limitedMany.replace("{minutes}", String(minutes))
}
