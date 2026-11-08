/**
 * Tela de novo aceite dos documentos legais, em `/legal/accept`.
 *
 * Camada: view (SDD 13.2). Recebe o retorno de `useLegalAccept` pela rota
 * `app/routes/legal-accept.tsx` e não chama a API. Usa `PageHeading`, o
 * `RequestIdCopy` e o `Button` e o `Spinner` de `components/ui`.
 *
 * SDD 13.3 (novo aceite) e 11.11 (versão dos documentos).
 */
import { Link } from "react-router"

import { PageHeading } from "@/app/page-heading.tsx"
import { RequestIdCopy } from "@/components/patterns/request-id-copy.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { pt } from "@/i18n/pt.ts"

import type { SubmitFailure } from "./model.ts"

/**
 * Mostra a versão nova, os links para os Termos e o Aviso e o botão de
 * aceite. Com o aceite em dia, como quando alguém abre a rota pelo menu,
 * mostra a confirmação e o link de volta para o `returnTo`.
 *
 * Uma falha aparece com `role="alert"`, para o leitor de tela anunciar, e
 * com o `request_id` copiável quando o servidor mandou um.
 */
export function LegalAcceptScreen({
  version,
  needsAcceptance,
  returnTo,
  pending,
  failure,
  accept,
}: {
  version: string | null
  needsAcceptance: boolean
  returnTo: string
  pending: boolean
  failure: SubmitFailure | null
  accept: () => Promise<void>
}) {
  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-6">
      <PageHeading title={pt.pages.legalAccept} />
      {needsAcceptance ? (
        <>
          {/* Sem a versão carregada, o marcador vira texto vazio. */}
          <p className="text-body text-foreground">
            {pt.legalAccept.lead.replace("{version}", version ?? "")}
          </p>
          <p className="flex flex-wrap gap-4 text-body text-foreground">
            <Link to="/terms" className="underline underline-offset-4">
              {pt.registration.termsLink}
            </Link>
            <Link to="/privacy" className="underline underline-offset-4">
              {pt.registration.privacyLink}
            </Link>
          </p>
          {failure ? (
            <div className="flex flex-col gap-2">
              <p role="alert" className="text-body text-danger">
                {failure.message}
              </p>
              {failure.requestId ? (
                <RequestIdCopy requestId={failure.requestId} />
              ) : null}
            </div>
          ) : null}
          {/* `min-h-11` dá o alvo de 44 px no celular (SDD 15.8). O texto
              do botão muda durante o pedido; o `Spinner` fica escondido
              do leitor de tela. */}
          <Button
            type="button"
            className="min-h-11 w-fit md:min-h-8"
            disabled={pending}
            onClick={() => {
              void accept()
            }}
          >
            {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
            {pending ? pt.legalAccept.accepting : pt.legalAccept.accept}
          </Button>
        </>
      ) : (
        <>
          <p role="status" className="text-body text-foreground">
            {pt.legalAccept.upToDate}
          </p>
          <Button asChild variant="link" className="h-11 w-fit px-0 md:h-8">
            <Link to={returnTo}>{pt.legalAccept.continue}</Link>
          </Button>
        </>
      )}
    </div>
  )
}
