/**
 * Os presets de movimento: uma função por animação do catálogo da seção
 * 16.3 (M1 a M16), num lugar só.
 *
 * Cada preset recebe o alvo e o `reduced` de `useMotion` e decide sozinho:
 * com movimento reduzido, usa `gsap.set` e põe o estado final direto; sem
 * redução, anima com os tokens de `tokens.ts`. Nenhum componente decide o
 * movimento reduzido por conta própria (seção 16.4), e `presets.test.ts`
 * confere o `gsap.set` de cada preset.
 *
 * As regras da seção 16.5 moram aqui: só `transform` e `opacity`;
 * `autoAlpha` nas entradas e saídas, que no zero também põe
 * `visibility: hidden`, e o elemento invisível não recebe clique;
 * `clearProps` no fim das entradas, para o CSS voltar a mandar;
 * `will-change` só durante a animação; e timelines em vez de `delay`.
 *
 * Quem usa: a casca (`app/shell.tsx`, M1), `useGsapPresence.ts` (M14) e
 * os componentes de `components/patterns` que animam.
 */
// Só o tipo: o plugin chega pelo argumento de moveSidebar, e este arquivo não o carrega.
import type { Flip } from "gsap/Flip"

import { gsap } from "./gsap.ts"
import { motionTokens } from "./tokens.ts"

/** O estado que `Flip.getState` registra, passado a `moveSidebar`. */
export type FlipState = ReturnType<typeof Flip.getState>

/**
 * Diz se há alvo para animar: texto, lista e `NodeList` vazios, `null` e
 * `undefined` não contam. Os presets checam antes de chamar o GSAP, que
 * avisa no console quando o alvo não existe, e chamam o `onComplete` mesmo
 * sem alvo.
 */
function canAnimate(target: gsap.TweenTarget) {
  if (typeof target === "string") {
    return target.length > 0
  }
  if (Array.isArray(target)) {
    return target.length > 0
  }
  if (typeof NodeList !== "undefined" && target instanceof NodeList) {
    return target.length > 0
  }
  return target != null
}

/**
 * A entrada comum de M1 e M14: de `from` para `to` em `duration.base`, com
 * `ease.enter` e `stagger.list` quando há vários alvos. Com movimento
 * reduzido, põe `to` direto e chama `onComplete` na hora.
 *
 * O caminho reduzido não limpa as propriedades: o `gsap.set` deixa em
 * linha o estado final, como `opacity: 1` e, com `y: 0`, um `transform`
 * neutro.
 */
function enter(
  target: gsap.TweenTarget,
  reduced: boolean,
  from: gsap.TweenVars,
  to: gsap.TweenVars,
  onComplete?: () => void
) {
  if (!canAnimate(target)) {
    onComplete?.()
    return
  }
  if (reduced) {
    gsap.set(target, { ...to, autoAlpha: 1 })
    onComplete?.()
    return
  }
  gsap.set(target, { willChange: "transform" })
  gsap.fromTo(target, from, {
    ...to,
    duration: motionTokens.duration.base,
    ease: motionTokens.ease.enter,
    stagger: motionTokens.stagger.list,
    clearProps: "transform,opacity,visibility,will-change",
    onComplete,
  })
}

/**
 * M1, a troca de rota: `autoAlpha` de 0 a 1 e `y` de `distance.enter`
 * (8 px) a 0. A casca passa os cards da página, que entram um a um, ou o
 * invólucro inteiro.
 */
export function enterRoute(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  enter(
    target,
    reduced,
    { autoAlpha: 0, y: motionTokens.distance.enter },
    { autoAlpha: 1, y: 0 },
    onComplete
  )
}

/**
 * Rótulos da barra lateral em M13. Recolhida, a barra esconde os rótulos com `sr-only`, e
 * eles continuam dando nome ao logotipo, à busca e aos grupos para o leitor de tela. Por isso
 * eles nunca ficam com `visibility: hidden`: só entram com `autoAlpha` quando a barra expande.
 *
 * @param visible Falso quando a barra recolhe: os rótulos só perdem as
 *   propriedades em linha e ficam com o `sr-only` do CSS.
 */
export function showSidebarLabels(
  target: gsap.TweenTarget,
  reduced: boolean,
  visible = true
) {
  if (!canAnimate(target)) {
    return
  }
  if (reduced || !visible) {
    gsap.set(target, { clearProps: "opacity,visibility" })
    return
  }
  gsap.fromTo(
    target,
    { autoAlpha: 0 },
    {
      autoAlpha: 1,
      duration: motionTokens.duration.fast,
      ease: motionTokens.ease.enter,
      overwrite: "auto",
      clearProps: "opacity,visibility",
    }
  )
}

/**
 * Ícones da barra lateral em M13. A largura troca direto, e o Flip leva cada ícone do estado
 * registrado no clique à posição nova. Com `scale`, o Flip usa só `transform`: sem ele, o
 * plugin anima `width` e `height` (seção 16.1). `simple: true` pula as
 * contas de rotação e inclinação, que os ícones não têm.
 *
 * @param state O estado que a barra registrou com `Flip.getState` antes de
 *   a classe mudar. Sem ele, ou sem o plugin, o preset só limpa o
 *   `transform`.
 * @param flip O plugin, passado pela barra lateral: este arquivo não o
 *   importa, para o Flip ficar fora do JavaScript inicial de `/`.
 */
export function moveSidebar(
  target: gsap.DOMTarget,
  reduced: boolean,
  state?: FlipState,
  flip?: Pick<typeof Flip, "from">
) {
  if (!canAnimate(target)) {
    return
  }
  if (reduced || !state || !flip) {
    gsap.set(target, { clearProps: "transform" })
    return
  }
  flip.from(state, {
    targets: target,
    duration: motionTokens.duration.base,
    ease: motionTokens.ease.move,
    scale: true,
    simple: true,
  })
}

/** M14, a entrada de diálogo e menu: `autoAlpha` e `scale` de 0,98 a 1. */
export function enterPresence(target: gsap.TweenTarget, reduced: boolean) {
  enter(
    target,
    reduced,
    { autoAlpha: 0, scale: 0.98 },
    { autoAlpha: 1, scale: 1 }
  )
}

/**
 * A entrada pela esquerda, com `autoAlpha` e `x` de `-distance` a 0. Serve
 * ao menu do celular, uma variação de M14 que a seção 16.3 não descreve.
 */
export function enterFromSide(
  target: gsap.TweenTarget,
  reduced: boolean,
  distance = 20
) {
  enter(
    target,
    reduced,
    { autoAlpha: 0, x: -Math.abs(distance) },
    { autoAlpha: 1, x: 0 }
  )
}

/**
 * M14, a saída: `autoAlpha` a 0 em `duration.fast` com `ease.exit` e, no
 * fim, `onComplete`, que desmonta o painel. Com movimento reduzido, some
 * direto.
 */
export function exitPresence(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  if (!canAnimate(target)) {
    onComplete?.()
    return
  }
  if (reduced) {
    gsap.set(target, { autoAlpha: 0, scale: 1 })
    onComplete?.()
    return
  }
  gsap.to(target, {
    autoAlpha: 0,
    duration: motionTokens.duration.fast,
    ease: motionTokens.ease.exit,
    onComplete,
  })
}

/** A saída do menu do celular, para a esquerda, par de `enterFromSide`. */
export function exitToSide(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void,
  distance = 20
) {
  if (!canAnimate(target)) {
    onComplete?.()
    return
  }
  if (reduced) {
    gsap.set(target, { autoAlpha: 0, x: 0 })
    onComplete?.()
    return
  }
  gsap.to(target, {
    autoAlpha: 0,
    x: -Math.abs(distance),
    duration: motionTokens.duration.fast,
    ease: motionTokens.ease.exit,
    onComplete,
  })
}

// Números do catálogo da seção 16.3 que não são tokens: o pulso do caret
// (M7), o intervalo entre as citações (M8) e o deslocamento da mensagem
// enviada (M5).
const caretPulseSeconds = 0.6
const citationStagger = 0.04
const userEnterDistance = 6

/**
 * A entrada genérica de M5, M6, M8 e M9: igual a `enter`, com duração e
 * intervalo opcionais e sem `stagger` quando não pedido.
 */
function fadeIn(
  target: gsap.TweenTarget,
  reduced: boolean,
  from: gsap.TweenVars,
  to: gsap.TweenVars,
  options?: { duration?: number; stagger?: number; onComplete?: () => void }
) {
  if (!canAnimate(target)) {
    options?.onComplete?.()
    return
  }
  if (reduced) {
    gsap.set(target, { ...to, autoAlpha: 1 })
    options?.onComplete?.()
    return
  }
  gsap.set(target, { willChange: "transform" })
  gsap.fromTo(target, from, {
    ...to,
    duration: options?.duration ?? motionTokens.duration.base,
    ease: motionTokens.ease.enter,
    stagger: options?.stagger,
    clearProps: "transform,opacity,visibility,will-change",
    onComplete: options?.onComplete,
  })
}

/** M5: a mensagem enviada entra com `autoAlpha` e `y` de 6 a 0. */
export function enterUserMessage(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  fadeIn(
    target,
    reduced,
    { autoAlpha: 0, y: userEnterDistance },
    { autoAlpha: 1, y: 0 },
    { onComplete }
  )
}

/**
 * M6: o contêiner da resposta aparece só com `autoAlpha`, quando o
 * `AssistantMessage` monta. Os tokens não animam um a um. O
 * `AssistantBubble` do cadastro usa o mesmo preset.
 *
 * A seção 16.3 põe o gatilho no evento `meta`. A mensagem do assistente
 * monta antes, no envio da pergunta, já no estado de espera, e é aí que a
 * entrada roda.
 */
export function enterAssistant(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  fadeIn(target, reduced, { autoAlpha: 0 }, { autoAlpha: 1 }, { onComplete })
}

/**
 * M7: o caret pulsa entre 1 e 0,3 de opacidade, em laço, enquanto a
 * resposta é gerada: o único laço do app (seção 16.1). Usa `opacity`, e
 * não `autoAlpha`, porque não é entrada nem saída. O laço acaba quando o
 * `StreamingCaret` sai da tela no `done`, e o `useGSAP` desfaz o tween.
 */
export function pulseCaret(target: gsap.TweenTarget, reduced: boolean) {
  if (!canAnimate(target)) {
    return
  }
  if (reduced) {
    gsap.set(target, { opacity: 1 })
    return
  }
  gsap.to(target, {
    opacity: 0.3,
    duration: caretPulseSeconds,
    repeat: -1,
    yoyo: true,
  })
}

/** M8: as citações entram uma a uma, a cada 0,04 s, com `scale` de 0,9 a 1. */
export function enterCitations(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  fadeIn(
    target,
    reduced,
    { autoAlpha: 0, scale: 0.9 },
    { autoAlpha: 1, scale: 1 },
    { stagger: citationStagger, onComplete }
  )
}

/**
 * M9, o evento `replace`: o rascunho sai e a resposta segura entra.
 *
 * Procura no alvo os filhos `data-outgoing`, o rascunho, e `data-incoming`,
 * a resposta nova. Com os dois, uma timeline tira o rascunho em
 * `duration.fast` e, só depois, traz a resposta em `duration.base`. Sem os
 * dois, faz uma entrada simples do alvo. Com movimento reduzido, troca
 * direto.
 */
export function replaceAnswer(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  const root = target instanceof Element ? target : null
  const outgoing = root?.querySelector("[data-outgoing]") ?? null
  const incoming = root?.querySelector("[data-incoming]") ?? null
  if (reduced) {
    if (outgoing) {
      gsap.set(outgoing, { autoAlpha: 0 })
    }
    if (incoming) {
      gsap.set(incoming, { autoAlpha: 1 })
    }
    if (!outgoing && !incoming) {
      gsap.set(target, { autoAlpha: 1 })
    }
    onComplete?.()
    return
  }
  if (!outgoing || !incoming) {
    fadeIn(target, false, { autoAlpha: 0 }, { autoAlpha: 1 }, { onComplete })
    return
  }
  const timeline = gsap.timeline({ onComplete })
  timeline.to(outgoing, {
    autoAlpha: 0,
    duration: motionTokens.duration.fast,
    ease: motionTokens.ease.exit,
  })
  timeline.fromTo(
    incoming,
    { autoAlpha: 0 },
    {
      autoAlpha: 1,
      duration: motionTokens.duration.base,
      ease: motionTokens.ease.enter,
      clearProps: "opacity,visibility",
    },
    // `">"` põe a entrada no fim do passo anterior da timeline: as duas não
    // se sobrepõem.
    ">"
  )
}

// M12: o deslocamento de entrada do `PasswordCard`.
const passwordEnterDistance = 12

/**
 * M10, campo entendido no `ProfileSummaryCard`: a camada `data-highlight`
 * acende e apaga, e ao mesmo tempo, na posição 0 da timeline, o ícone
 * `data-confirm` cresce de 0,6 a 1 com `ease.confirm`, a curva que só este
 * ícone usa (seção 16.2). Com movimento reduzido, só o ícone aparece, sem
 * destaque.
 */
export function confirmField(target: gsap.TweenTarget, reduced: boolean) {
  if (!canAnimate(target)) {
    return
  }
  const root = target instanceof Element ? target : null
  const highlight = root?.querySelector("[data-highlight]") ?? null
  const icon = root?.querySelector("[data-confirm]") ?? null
  if (reduced) {
    if (highlight) {
      gsap.set(highlight, { autoAlpha: 0 })
    }
    if (icon) {
      gsap.set(icon, { autoAlpha: 1, scale: 1 })
    }
    if (!highlight && !icon) {
      gsap.set(target, { autoAlpha: 1 })
    }
    return
  }
  const flash = highlight ?? target
  const sequence = gsap.timeline()
  sequence.fromTo(
    flash,
    { autoAlpha: 0 },
    {
      autoAlpha: 1,
      duration: motionTokens.duration.fast,
      ease: motionTokens.ease.enter,
    }
  )
  sequence.to(flash, {
    autoAlpha: 0,
    duration: motionTokens.duration.base,
    ease: motionTokens.ease.exit,
    clearProps: "opacity,visibility",
  })
  if (icon) {
    sequence.fromTo(
      icon,
      { scale: 0.6, autoAlpha: 0 },
      {
        scale: 1,
        autoAlpha: 1,
        duration: motionTokens.duration.base,
        ease: motionTokens.ease.confirm,
        clearProps: "transform,opacity,visibility",
      },
      0
    )
  }
}

/**
 * M11, a barra de progresso do `RegistrationStepper`, que hoje fica fora
 * da tela de cadastro e só aparece no Storybook (seção 14.6): muda o
 * `scaleX` a partir da esquerda, com `ease.move`.
 */
export function moveStepper(
  target: gsap.TweenTarget,
  reduced: boolean,
  scale = 1
) {
  if (!canAnimate(target)) {
    return
  }
  if (reduced) {
    gsap.set(target, { scaleX: scale, transformOrigin: "left center" })
    return
  }
  gsap.to(target, {
    scaleX: scale,
    transformOrigin: "left center",
    duration: motionTokens.duration.slow,
    ease: motionTokens.ease.move,
  })
}

/**
 * M12: o `PasswordCard` entra com `autoAlpha` e `y` de 12 a 0 em
 * `duration.slow`. O cartão põe o foco no campo no `onComplete`, que com
 * movimento reduzido roda na hora: o foco chega nos dois casos (seção
 * 16.6).
 */
export function enterPassword(
  target: gsap.TweenTarget,
  reduced: boolean,
  onComplete?: () => void
) {
  if (!canAnimate(target)) {
    onComplete?.()
    return
  }
  if (reduced) {
    gsap.set(target, { autoAlpha: 1, y: 0 })
    onComplete?.()
    return
  }
  gsap.set(target, { willChange: "transform" })
  gsap.fromTo(
    target,
    { autoAlpha: 0, y: passwordEnterDistance },
    {
      autoAlpha: 1,
      y: 0,
      duration: motionTokens.duration.slow,
      ease: motionTokens.ease.enter,
      clearProps: "transform,opacity,visibility,will-change",
      onComplete,
    }
  )
}

/**
 * M16, o toque num botão: `scale` de 0,98 a 1 em `duration.instant`.
 * Nenhum componente chama este preset hoje: o `Button` de `components/ui`
 * não tem esse efeito.
 */
export function press(target: gsap.TweenTarget, reduced: boolean) {
  if (!canAnimate(target)) {
    return
  }
  if (reduced) {
    gsap.set(target, { scale: 1 })
    return
  }
  gsap.fromTo(
    target,
    { scale: 0.98 },
    {
      scale: 1,
      duration: motionTokens.duration.instant,
      ease: motionTokens.ease.enter,
      clearProps: "transform",
    }
  )
}

// M4: o tempo com que cursor e tooltip alcançam o ponteiro.
const pointerSeconds = 0.2

/**
 * M2: o número visível sobe de 0 ao valor, com snap. O aria-label fica com
 * o componente.
 *
 * O GSAP anima um objeto comum, `counter`, e o `onUpdate` escreve o número
 * formatado no texto. O `snap` arredonda cada passo a `decimals` casas:
 * zero dá inteiros, como pede a seção 16.3; as taxas da visão geral passam
 * 3, porque vão de 0 a 1. A duração é `duration.chart` (0,8 s), embora a
 * seção 16.1 reserve os 800 ms à revelação de gráfico.
 */
export function countUp(
  target: gsap.TweenTarget,
  reduced: boolean,
  value = 0,
  format: (value: number) => string = (current) => String(current),
  decimals = 0
) {
  if (!canAnimate(target)) {
    return
  }
  const element = target instanceof Element ? target : null
  if (reduced) {
    gsap.set(target, { autoAlpha: 1 })
    if (element) {
      element.textContent = format(value)
    }
    return
  }
  const counter = { value: 0 }
  const step = 1 / 10 ** decimals
  gsap.to(counter, {
    value,
    duration: motionTokens.duration.chart,
    ease: motionTokens.ease.enter,
    snap: { value: step },
    onUpdate: () => {
      if (element) {
        element.textContent = format(counter.value)
      }
    },
  })
}

/**
 * M3: área e linha se revelam da esquerda com scaleX, em `duration.chart`
 * e `ease.move`.
 */
export function revealChart(target: gsap.TweenTarget, reduced: boolean) {
  if (!canAnimate(target)) {
    return
  }
  if (reduced) {
    gsap.set(target, { scaleX: 1, transformOrigin: "left center" })
    return
  }
  gsap.fromTo(
    target,
    { scaleX: 0, transformOrigin: "left center" },
    {
      scaleX: 1,
      duration: motionTokens.duration.chart,
      ease: motionTokens.ease.move,
      clearProps: "transform",
    }
  )
}

/**
 * M4: cursor e tooltip seguem o ponteiro com quickTo. Devolve a função que
 * move.
 *
 * `gsap.quickTo` cria uma vez a função que reaproveita a mesma animação a
 * cada chamada, sem criar um tween novo a cada movimento do mouse. Com
 * movimento reduzido, a função devolvida pula para a posição com
 * `gsap.set`.
 */
export function followPointer(target: gsap.TweenTarget, reduced: boolean) {
  if (reduced || !canAnimate(target)) {
    gsap.set(target, { x: 0, y: 0 })
    return (x: number, y: number) => {
      gsap.set(target, { x, y })
    }
  }
  const moveX = gsap.quickTo(target, "x", {
    duration: pointerSeconds,
    ease: motionTokens.ease.enter,
  })
  const moveY = gsap.quickTo(target, "y", {
    duration: pointerSeconds,
    ease: motionTokens.ease.enter,
  })
  return (x: number, y: number) => {
    moveX(x)
    moveY(y)
  }
}

/**
 * M15: cada segmento vai ao `data-scale` dele com scaleX. O valor é uma
 * função, que o GSAP chama para cada elemento do alvo.
 */
export function moveSegments(target: gsap.TweenTarget, reduced: boolean) {
  if (!canAnimate(target)) {
    return
  }
  const scaleOf = (_index: number, element: Element) =>
    Number((element as HTMLElement).dataset.scale ?? "0")
  if (reduced) {
    gsap.set(target, { scaleX: scaleOf, transformOrigin: "left center" })
    return
  }
  gsap.to(target, {
    scaleX: scaleOf,
    transformOrigin: "left center",
    duration: motionTokens.duration.slow,
    ease: motionTokens.ease.move,
  })
}

/**
 * Todos os presets num objeto: os componentes importam `presets` e chamam
 * `presets.enterRoute(...)`, e o teste percorre a lista inteira com
 * movimento reduzido.
 */
/**
 * Atendimento humano (seção 29.11): o `HandoffStatusBar` ao mudar de estado
 * e um item novo da `QueueList` entram como a troca de rota, com
 * `autoAlpha` e `y` de 8 a 0 em `duration.base`, e vários itens com
 * `stagger.list`. Com movimento reduzido, aparecem direto.
 */
export function enterHandoffStatus(
  target: gsap.TweenTarget,
  reduced: boolean
) {
  enter(
    target,
    reduced,
    { autoAlpha: 0, y: motionTokens.distance.enter },
    { autoAlpha: 1, y: 0 }
  )
}

/** A mensagem da equipe ao chegar usa o preset do M5 (seção 29.11). */
export function enterAttendantMessage(
  target: gsap.TweenTarget,
  reduced: boolean
) {
  enterUserMessage(target, reduced)
}

export const presets = {
  enterRoute,
  enterHandoffStatus,
  enterQueueItem: enterHandoffStatus,
  enterAttendantMessage,
  showSidebarLabels,
  moveSidebar,
  enterPresence,
  enterFromSide,
  exitPresence,
  exitToSide,
  enterUserMessage,
  enterAssistant,
  pulseCaret,
  enterCitations,
  replaceAnswer,
  confirmField,
  moveStepper,
  enterPassword,
  press,
  countUp,
  revealChart,
  followPointer,
  moveSegments,
}
