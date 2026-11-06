/**
 * Cabeçalhos de segurança da seção 13.4 do SDD, num lugar só.
 *
 * A Vercel aplica estes cabeçalhos em produção (`vercel.ts`). O `vite preview` aplica os
 * mesmos na e2e da CI (`vite.config.ts`), para uma violação de CSP aparecer antes do deploy.
 */
export const contentSecurityPolicy = [
  "default-src 'self'",
  // O Radix trava a rolagem de diálogos e sheets com um <style> injetado
  // (react-remove-scroll). Estilo em linha não executa código; script-src continua 'self'.
  "style-src 'self' 'unsafe-inline'",
  "connect-src 'self'",
  "img-src 'self' data:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ")

export const securityHeaders: Record<string, string> = {
  "Content-Security-Policy": contentSecurityPolicy,
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
