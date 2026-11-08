/**
 * Tela inicial `/`: responder à primeira pergunta sem atrito. Seção 15.5 do
 * SDD (Início) e princípio 1 da seção 15.1.
 *
 * View: recebe o estado e o `onAsk` de `useAskConversation`, por
 * `app/routes/home.tsx`, e não chama a API. Usa `Composer` e
 * `SafetyNotice`, de `components/patterns`, e as `SuggestionChips` desta
 * pasta.
 */
import { useState } from "react"
import { Link } from "react-router"

import { Composer } from "@/components/patterns/composer.tsx"
import { SafetyNotice } from "@/components/patterns/safety-notice.tsx"
import { PageHeading } from "@/app/page-heading.tsx"
import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

import { SuggestionChips } from "./suggestion-chips.tsx"

/**
 * Título, compositor, sugestões, aviso de segurança e os links para
 * Cadastrar e Entrar.
 *
 * Com `budgetExceeded`, o compositor e as sugestões ficam desabilitados, e
 * o compositor mostra o texto de indisponibilidade com o telefone da mesa.
 * O `error` da criação da conversa aparece no próprio campo.
 */
export function HomeScreen({
  pending,
  error,
  budgetExceeded,
  onAsk,
}: {
  pending: boolean
  error: string | null
  budgetExceeded: boolean
  onAsk: (text: string) => void
}) {
  // O texto digitado é estado da view. O hook só recebe o envio.
  const [value, setValue] = useState("")

  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col gap-6">
      <PageHeading title={pt.home.title} variant="display" />
      <Composer
        value={value}
        onChange={setValue}
        onSubmit={() => {
          const text = value.trim()
          if (!text) {
            return
          }
          onAsk(text)
          // O campo é limpo antes de saber se o envio deu certo. A Etapa
          // 14.2 só limpa depois do envio aceito.
          setValue("")
        }}
        // A tela inicial nunca tem resposta em andamento, então não há o
        // que parar.
        onStop={() => undefined}
        streaming={false}
        pending={pending}
        disabled={budgetExceeded}
        disabledReason={budgetExceeded ? pt.ask.unavailable : null}
        error={error}
      />
      <SuggestionChips disabled={budgetExceeded || pending} onSelect={onAsk} />
      <SafetyNotice />
      {/* Alvos de 44 px no celular e 32 px no desktop (seção 15.8). O
          texto de Entrar é curto, e `min-w-11` garante a largura. */}
      <div className="flex flex-wrap gap-4">
        <Button asChild variant="link" className="h-11 px-0 md:h-8">
          <Link to="/register">{pt.nav.register}</Link>
        </Button>
        <Button asChild variant="link" className="h-11 min-w-11 px-0 md:h-8">
          <Link to="/sign-in">{pt.nav.signIn}</Link>
        </Button>
      </div>
    </div>
  )
}
