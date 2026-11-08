/**
 * Rota `/`, o início: o título, o compositor, as sugestões e o aviso de
 * segurança (seção 15.5).
 *
 * Usa o mesmo controller da conversa, `useAskConversation`, sem `id`. A
 * primeira pergunta cria a conversa com `POST /v1/conversations`, guarda o
 * texto e leva a `/ask/:id`, onde a pergunta é enviada e a resposta chega.
 * O módulo vai como `modulepreload` no `index.html` (`vite.config.ts`).
 */
import { HomeScreen } from "@/features/ask/home-screen.tsx"
import { useAskConversation } from "@/features/ask/useAskConversation.ts"

/** Passa à tela só o que o início usa: envio, erro e orçamento. */
export function Component() {
  const ask = useAskConversation(undefined)
  return (
    <HomeScreen
      pending={ask.pending}
      error={ask.error}
      budgetExceeded={ask.budgetExceeded}
      onAsk={ask.ask}
    />
  )
}
