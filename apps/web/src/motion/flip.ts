/**
 * O plugin Flip do GSAP, registrado à parte (seção 16.2).
 *
 * O Flip anima uma mudança de layout: `Flip.getState` registra a posição e
 * o tamanho dos elementos, o layout muda, e `Flip.from` leva cada elemento
 * do estado registrado ao novo. Quem usa: a barra lateral
 * (`components/patterns/app-sidebar.tsx`), que registra o estado no clique
 * e passa o plugin ao preset `moveSidebar` de `presets.ts`.
 */
import { Flip } from "gsap/Flip"

import { gsap } from "./gsap.ts"

// Só a M13 usa o Flip (SDD 16.3). Quem importa este arquivo é a barra lateral, que carrega sob
// demanda, e o plugin fica fora do JavaScript inicial de `/` (seção 5.3).
gsap.registerPlugin(Flip)

export { Flip }
