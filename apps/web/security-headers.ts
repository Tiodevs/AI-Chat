/**
 * Cabeçalhos de segurança da seção 13.4 do SDD, num lugar só.
 *
 * A Vercel aplica estes cabeçalhos em produção (`vercel.ts`). O `vite preview` aplica os
 * mesmos na e2e da CI (`vite.config.ts`), para uma violação de CSP aparecer antes do deploy.
 *
 * Quem usa: `vercel.ts`, `vite.config.ts` e o teste
 * `src/deploy/vercel-config.test.ts`. A e2e ao vivo falha se o navegador
 * registrar uma violação de CSP (`e2e/live/fixtures.ts`). Faltam
 * `Cross-Origin-Opener-Policy` e um HSTS próprio: a Etapa 15.2 os
 * acrescenta aqui.
 */

/**
 * A Content Security Policy: de onde a página pode carregar cada tipo de
 * recurso. `default-src 'self'` vale para o que não tem diretiva própria,
 * como scripts e fontes: só da própria origem, sem script em linha. Por
 * isso as fontes Geist vêm do build, e não de um serviço externo.
 */
export const contentSecurityPolicy = [
  "default-src 'self'",
  // O Radix trava a rolagem de diálogos e sheets com um <style> injetado
  // (react-remove-scroll). Estilo em linha não executa código; script-src continua 'self'.
  "style-src 'self' 'unsafe-inline'",
  // `fetch` e o fluxo SSE só para a própria origem, que é o `/backend`.
  "connect-src 'self'",
  "img-src 'self' data:",
  // Nenhum site pode pôr o app num `iframe`.
  "frame-ancestors 'none'",
  // Ninguém troca a base dos endereços relativos com uma tag `base`.
  "base-uri 'self'",
  // Formulários só enviam para a própria origem.
  "form-action 'self'",
].join("; ")

/**
 * Todos os cabeçalhos: a CSP, `nosniff`, que impede o navegador de
 * adivinhar o tipo de um arquivo, a política de `Referer`, que manda só a
 * origem para outros sites, e a `Permissions-Policy`, que desliga câmera,
 * microfone e geolocalização.
 */
export const securityHeaders: Record<string, string> = {
  "Content-Security-Policy": contentSecurityPolicy,
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
