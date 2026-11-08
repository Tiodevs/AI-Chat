/**
 * Ponto de entrada do frontend. O `index.html` carrega este módulo, e ele
 * monta o React no `div` de id `root`.
 *
 * A ordem dos invólucros é a da inicialização: `StrictMode`, os provedores
 * de `app/providers.tsx` (o cache do TanStack Query e o contexto de
 * movimento) e, dentro deles, o roteador de `app/router.tsx`. Assim toda
 * rota alcança o cache e o `useMotion`. O import de `globals.css` traz o
 * Tailwind, as fontes Geist e os tokens de cor.
 *
 * Quem usa: o `<script type="module">` do `index.html`; no build, o Vite
 * troca esse caminho pelo arquivo com hash em `/assets`. SDD 13.1 e 13.2.
 */
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { RouterProvider } from "react-router"

import { AppProviders } from "@/app/providers.tsx"
import { router } from "@/app/router.tsx"
import "@/styles/globals.css"

// O `div` vem do `index.html`. Sem ele não há onde montar o app, e o erro
// diz o motivo no console.
const root = document.getElementById("root")
if (!root) {
  throw new Error("Elemento #root ausente")
}

// `StrictMode` só age em desenvolvimento: roda a renderização e os efeitos
// duas vezes, para expor efeito colateral fora do lugar. O build de
// produção não faz essa checagem.
createRoot(root).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
