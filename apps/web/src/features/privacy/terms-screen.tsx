/**
 * Termos de Uso, em `/terms`: a versão vigente e as seções do texto.
 *
 * Camada: view (SDD 13.2). Recebe a versão de `useLegalVersions` pela rota
 * `app/routes/terms.tsx` e não chama a API. O texto mora em
 * `pt.termsOfUse`, de `i18n/pt.ts` (SDD 15.7). Usa o `PageHeading`.
 *
 * SDD 11.11 (documentos de privacidade).
 */
import { Link } from "react-router"

import { PageHeading } from "@/app/page-heading.tsx"
import { pt } from "@/i18n/pt.ts"

/**
 * Mostra cada seção com o `id` como âncora e o título como nome da região,
 * e termina com o link para o Aviso de Privacidade. Sem a versão carregada,
 * a linha da versão some.
 */
export function TermsScreen({ version }: { version: string | null }) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8">
      <div className="flex flex-col gap-2">
        <PageHeading title={pt.pages.terms} />
        {version ? (
          <p className="text-label text-muted-foreground">
            {pt.termsOfUse.version.replace("{version}", version)}
          </p>
        ) : null}
        <p className="text-body text-foreground">{pt.privacyNotice.fictional}</p>
      </div>
      {pt.termsOfUse.sections.map((section) => (
        <section
          key={section.id}
          id={section.id}
          aria-labelledby={`${section.id}-title`}
          className="flex scroll-mt-6 flex-col gap-3"
        >
          <h2
            id={`${section.id}-title`}
            className="text-title text-foreground-strong"
          >
            {section.title}
          </h2>
          {section.body.map((paragraph) => (
            <p key={paragraph} className="text-body text-foreground">
              {paragraph}
            </p>
          ))}
        </section>
      ))}
      <Link
        to="/privacy"
        className="inline-flex min-h-11 w-fit items-center text-body text-foreground underline underline-offset-4 md:min-h-6"
      >
        {pt.termsOfUse.privacyLink}
      </Link>
    </div>
  )
}
