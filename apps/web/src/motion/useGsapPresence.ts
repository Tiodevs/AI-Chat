/**
 * A entrada e a saída animadas de um painel que abre e fecha (M14, seção
 * 16.3).
 *
 * Quem usa: a busca (`components/patterns/search-dialog.tsx`, com
 * `forceMount` no `DialogContent` do Radix, para o GSAP controlar a
 * montagem), o menu do visitante (`guest-header.tsx`) e o menu do celular
 * (`app-sidebar.tsx`, que entra pela lateral). Usa os presets
 * `enterPresence`, `exitPresence`, `enterFromSide` e `exitToSide`.
 */
import { useState } from "react"

import { useGSAP } from "./gsap.ts"
import { useMotion } from "./MotionProvider.tsx"
import { presets } from "./presets.ts"

/**
 * Diz se o painel deve estar montado e anima a troca.
 *
 * A ideia: ao fechar, o painel continua montado até a saída terminar, e só
 * então sai da árvore. Por isso quem usa monta o painel quando o retorno é
 * verdadeiro, e não quando `open` é verdadeiro.
 *
 * O código não cumpre isso hoje. `rendered` só começa `true` quando o
 * painel já nasce aberto, e nada o liga depois. Num painel que abre depois
 * da montagem, fechar põe o retorno em `false` no mesmo render, e o painel
 * desmonta sem a saída. A Etapa 14.3 corrige.
 *
 * @param open Se o painel deve estar aberto.
 * @param ref O elemento que anima; também é o `scope` do `useGSAP`.
 * @param fromX Zero para entrar com escala. Outro valor faz o painel entrar
 *   e sair pela esquerda, deslocado `Math.abs(fromX)` px.
 * @returns `true` enquanto o painel deve ficar montado.
 */
export function useGsapPresence(
  open: boolean,
  ref: { current: HTMLElement | null },
  fromX = 0,
) {
  const { reduced } = useMotion()
  const [rendered, setRendered] = useState(open)
  const mounted = open || rendered

  useGSAP(
    () => {
      const node = ref.current
      if (!node || !mounted) {
        return
      }
      // Quando a saída termina, o painel pode sair da árvore.
      const finish = () => {
        setRendered(false)
      }
      if (open) {
        if (fromX === 0) {
          presets.enterPresence(node, reduced)
        } else {
          presets.enterFromSide(node, reduced, Math.abs(fromX))
        }
        return
      }
      if (fromX === 0) {
        presets.exitPresence(node, reduced, finish)
      } else {
        presets.exitToSide(node, reduced, finish, Math.abs(fromX))
      }
    },
    { dependencies: [open, mounted, reduced, fromX], scope: ref },
  )

  return mounted
}
