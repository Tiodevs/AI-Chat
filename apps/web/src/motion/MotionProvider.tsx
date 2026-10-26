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

export type MotionPreference = "system" | "on" | "off"

const STORAGE_KEY = "atrium.motion-preference"

type MotionContextValue = {
  reduced: boolean
  isDesktop: boolean
  isMobile: boolean
  preference: MotionPreference
  setPreference: (preference: MotionPreference) => void
}

const MotionContext = createContext<MotionContextValue | null>(null)

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

function resolveReduced(preference: MotionPreference, systemReduced: boolean) {
  if (preference === "on") {
    return true
  }
  if (preference === "off") {
    return false
  }
  return systemReduced
}

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

export function MotionProvider({ children }: { children: ReactNode }) {
  const [motion, setMotion] = useState(readMedia)

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

  useEffect(() => {
    document.documentElement.dataset.motion = motion.reduced ? "reduce" : "full"
  }, [motion.reduced])

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

  const value = useMemo(
    () => ({
      ...motion,
      setPreference,
    }),
    [motion, setPreference],
  )

  return <MotionContext.Provider value={value}>{children}</MotionContext.Provider>
}

export function useMotion() {
  const context = useContext(MotionContext)
  if (!context) {
    throw new Error("useMotion deve ficar dentro de MotionProvider")
  }
  return context
}
