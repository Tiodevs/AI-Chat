import { Flip } from "gsap/Flip"

import { gsap } from "./gsap.ts"

// Só a M13 usa o Flip (SDD 16.3). Quem importa este arquivo é a barra lateral, que carrega sob
// demanda, e o plugin fica fora do JavaScript inicial de `/` (seção 5.3).
gsap.registerPlugin(Flip)

export { Flip }
