/**
 * O contexto de movimento: decide se o app anima e diz a largura da tela
 * (seção 16.4).
 *
 * Junta a preferência do sistema, `prefers-reduced-motion`, com a da
 * pessoa, Reduce motion, guardada no `localStorage` com os valores System,
 * On e Off da seção 15.5 (`system`, `on` e `off`). Também expõe
 * `isDesktop` (1024 px ou mais) e `isMobile` (abaixo de 768 px), as
 * larguras da seção 14.5; entre as duas fica o tablet.
 *
 * Quem usa: `app/providers.tsx` monta o provedor. A casca, os componentes
 * que animam, o `ProfileButton` e a aba Perfil da conta leem `useMotion`.
 * Os presets de `presets.ts` recebem o `reduced` daqui: nenhum componente
 * decide o movimento reduzido sozinho.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import { gsap } from "./gsap.ts"

/**
 * A preferência da pessoa: `system` segue o sistema, `on` reduz o
 * movimento sempre e `off` anima sempre, mesmo com o sistema pedindo
 * redução.
 */
export type MotionPreference = "system" | "on" | "off"

// A preferência fica neste navegador e não vai para o servidor (Aviso de
// Privacidade, seção Cookies, em `pt.privacyNotice`).
const STORAGE_KEY = "atrium.motion-preference"

/** O que `useMotion` devolve. */
type MotionContextValue = {
  reduced: boolean
  isDesktop: boolean
  isMobile: boolean
  preference: MotionPreference
  setPreference: (preference: MotionPreference) => void
}

const MotionContext = createContext<MotionContextValue | null>(null)

/**
 * Lê a preferência gravada. Um valor desconhecido, ou um `localStorage`
 * bloqueado, que lança erro ao ser lido, vale como `system`.
 */
function readPreference(): MotionPreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === "system" || stored === "on" || stored === "off") {
      return stored
    }
  } catch {
    return "system"
  }
  return "system"
}

/** Aplica a preferência da pessoa por cima da do sistema. */
function resolveReduced(preference: MotionPreference, systemReduced: boolean) {
  if (preference === "on") {
    return true
  }
  if (preference === "off") {
    return false
  }
  return systemReduced
}

/**
 * O estado inicial, lido direto do `matchMedia` na montagem: a primeira
 * renderização já sabe a largura da tela e se reduz o movimento.
 */
function readMedia() {
  const preference = readPreference()
  return {
    reduced: resolveReduced(
      preference,
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
    isDesktop: window.matchMedia("(min-width: 1024px)").matches,
    isMobile: window.matchMedia("(max-width: 767px)").matches,
    preference,
  }
}

/**
 * O provedor do contexto de movimento.
 *
 * 1. Lê o estado inicial do `matchMedia` e do `localStorage`.
 * 2. Cria um `gsap.matchMedia()` com as três condições. O GSAP chama a
 *    função quando alguma delas casa e de novo quando alguma muda, e o
 *    estado acompanha.
 * 3. Grava `data-motion` (`reduce` ou `full`) no `html`. O `globals.css`
 *    usa o atributo para cortar as animações e transições de CSS.
 * 4. `setPreference` grava a escolha e chama `gsap.matchMediaRefresh()`.
 *
 * Efeitos colaterais: `localStorage`, o atributo `data-motion` do `html` e
 * os ouvintes de mídia do GSAP, desfeitos com `revert` ao desmontar.
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  // 1. A função vai sem chamar: o `useState` a roda só na primeira vez.
  const [motion, setMotion] = useState(readMedia)

  // 2. Atenção: quando nenhuma condição casa, como no tablet (768 a
  // 1023 px) sem redução no sistema, o GSAP não chama a função. Ao
  // redimensionar do desktop ou do celular para essa faixa, `isDesktop` e
  // `isMobile` ficam com o valor anterior até outra condição casar.
  useEffect(() => {
    const media = gsap.matchMedia()
    media.add(
      {
        reduceMotion: "(prefers-reduced-motion: reduce)",
        isDesktop: "(min-width: 1024px)",
        isMobile: "(max-width: 767px)",
      },
      (context) => {
        const conditions = context.conditions
        const preference = readPreference()
        setMotion({
          reduced: resolveReduced(
            preference,
            Boolean(conditions?.reduceMotion),
          ),
          isDesktop: Boolean(conditions?.isDesktop),
          isMobile: Boolean(conditions?.isMobile),
          preference,
        })
      },
    )
    return () => {
      media.revert()
    }
  }, [])

  // 3. `reduce` corta as animações e transições de CSS; `full` as deixa
  // rodar mesmo com o sistema pedindo redução, para a preferência Off.
  useEffect(() => {
    document.documentElement.dataset.motion = motion.reduced ? "reduce" : "full"
  }, [motion.reduced])

  /**
   * 4. Grava a preferência e aplica na hora. `matchMediaRefresh` faz o
   * GSAP reler as condições e rodar de novo as funções de `matchMedia` que
   * casam. O `setItem` não tem `try`: com o `localStorage` bloqueado, ele
   * lança e a preferência não muda. A Etapa 14.3 o protege.
   */
  const setPreference = useCallback((preference: MotionPreference) => {
    localStorage.setItem(STORAGE_KEY, preference)
    const systemReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches
    setMotion((current) => ({
      ...current,
      preference,
      reduced: resolveReduced(preference, systemReduced),
    }))
    gsap.matchMediaRefresh()
  }, [])

  // O objeto do contexto só muda quando o estado muda: quem lê `useMotion`
  // não renderiza de novo à toa.
  const value = useMemo(
    () => ({
      ...motion,
      setPreference,
    }),
    [motion, setPreference],
  )

  return <MotionContext.Provider value={value}>{children}</MotionContext.Provider>
}

/**
 * Lê o contexto de movimento: `reduced`, `isDesktop`, `isMobile`, a
 * preferência e `setPreference`. Lança fora do `MotionProvider`, para um
 * componente montado sem o provedor falhar logo.
 */
export function useMotion() {
  const context = useContext(MotionContext)
  if (!context) {
    throw new Error("useMotion deve ficar dentro de MotionProvider")
  }
  return context
}
