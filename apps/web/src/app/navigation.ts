import {
  Activity,
  BadgeCheck,
  ClipboardList,
  FileText,
  Files,
  Inbox,
  LayoutDashboard,
  LogIn,
  MessageSquarePlus,
  MessagesSquare,
  Shield,
  Sparkles,
  UserPlus,
  UserRound,
  type LucideIcon,
} from "lucide-react"

import { pt } from "@/i18n/pt.ts"

export type NavItem = {
  label: string
  to: string
  icon: LucideIcon
  end?: boolean
}

export type NavGroup = {
  label: string
  items: NavItem[]
}

export const navigation: NavGroup[] = [
  {
    label: pt.nav.assistant,
    items: [
      {
        label: pt.nav.newQuestion,
        to: "/",
        icon: MessageSquarePlus,
        end: true,
      },
      {
        label: pt.nav.conversations,
        to: "/ask",
        icon: MessagesSquare,
      },
    ],
  },
  {
    label: pt.nav.account,
    items: [
      { label: pt.nav.register, to: "/register", icon: UserPlus, end: true },
      {
        label: pt.nav.registerForm,
        to: "/register/form",
        icon: ClipboardList,
        end: true,
      },
      { label: pt.nav.signIn, to: "/sign-in", icon: LogIn, end: true },
      { label: pt.nav.accountPage, to: "/account", icon: UserRound, end: true },
      { label: pt.nav.privacy, to: "/privacy", icon: Shield, end: true },
      { label: pt.nav.terms, to: "/terms", icon: FileText, end: true },
      {
        label: pt.nav.legalAccept,
        to: "/legal/accept",
        icon: BadgeCheck,
        end: true,
      },
    ],
  },
  {
    label: pt.nav.operations,
    items: [
      {
        label: pt.nav.overview,
        to: "/admin",
        icon: LayoutDashboard,
        end: true,
      },
      { label: pt.nav.documents, to: "/admin/documents", icon: Files, end: true },
      { label: pt.nav.quality, to: "/admin/quality", icon: Activity, end: true },
    ],
  },
  {
    label: pt.nav.system,
    items: [
      {
        label: pt.nav.privacyRequests,
        to: "/admin/privacy",
        icon: Inbox,
        end: true,
      },
    ],
  },
]

/** Quem está vendo o app. `guest` é o visitante sem sessão. SDD 14.5. */
export type Viewer = "guest" | "member" | "admin"

const guestOnly = new Set<string>(["/register", "/register/form", "/sign-in"])
const adminGroups = new Set<string>([pt.nav.operations, pt.nav.system])

export function viewerOf(role: string | null | undefined): Viewer {
  if (role === "admin") {
    return "admin"
  }
  return role ? "member" : "guest"
}

/** Grupos que fazem sentido para quem vê: sem cadastro e entrada para quem já entrou, operação só para admin. */
export function navigationFor(viewer: Viewer): NavGroup[] {
  return navigation
    .filter((group) => viewer === "admin" || !adminGroups.has(group.label))
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => viewer === "guest" || !guestOnly.has(item.to)
      ),
    }))
    .filter((group) => group.items.length > 0)
}

export function flattenNavigation(viewer: Viewer) {
  return navigationFor(viewer).flatMap((group) => group.items)
}

/** Ações do cabeçalho de quem ainda não entrou. */
export const guestActions = [
  { label: pt.nav.signIn, to: "/sign-in", icon: LogIn, variant: "ghost" },
  {
    label: pt.nav.registerForm,
    to: "/register/form",
    icon: ClipboardList,
    variant: "outline",
  },
  {
    label: pt.nav.registerWithAi,
    to: "/register",
    icon: Sparkles,
    variant: "default",
  },
] as const
