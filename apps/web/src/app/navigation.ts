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

export function flattenNavigation() {
  return navigation.flatMap((group) => group.items)
}
