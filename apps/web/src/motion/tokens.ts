/**
 * Os tokens de movimento da seção 16.2, em segundos e pixels, as unidades
 * que o GSAP espera.
 *
 * Quem usa: `gsap.ts`, nos padrões globais, e `presets.ts`, em cada
 * animação. Nenhum componente lê estes números direto: anima pelos
 * presets.
 */

/**
 * `duration`: `instant` para hover e toque, `fast` para saídas, tooltips e
 * menus, `base` para entradas de conteúdo (o padrão global), `slow` para
 * troca de passo e cartões grandes, e `chart` para a revelação de gráfico.
 * `ease`: entrada, saída, mudança de posição e o ícone de confirmação de
 * campo, a única curva que passa do ponto e volta. `stagger.list` separa a
 * entrada de cards e listas, e `distance.enter` é o deslocamento vertical
 * de entrada. `as const` deixa cada valor com o tipo literal.
 */
export const motionTokens = {
  duration: {
    instant: 0.12,
    fast: 0.18,
    base: 0.28,
    slow: 0.45,
    chart: 0.8,
  },
  ease: {
    enter: "power2.out",
    exit: "power2.in",
    move: "power3.inOut",
    confirm: "back.out(2)",
  },
  stagger: {
    list: 0.05,
  },
  distance: {
    enter: 8,
  },
} as const
