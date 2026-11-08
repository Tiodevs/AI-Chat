/**
 * O ponto de entrada da pasta `lib/api`: reexporta o cliente `api`.
 *
 * Nenhum arquivo do app importa este caminho hoje: os hooks de feature
 * importam `client.ts` direto, e os tipos, de `schema.ts`. O nome
 * `@/lib/api` aparece no teste das regras do ESLint
 * (`src/eslint/restrictions.test.ts`), que confere que só os hooks de
 * feature podem importá-lo (seção 6.2).
 */
export { api } from "./client.ts"
