/**
 * Os destinos da navegação: os grupos da barra lateral, a lista da busca
 * ⌘K, as ações do cabeçalho do visitante e o filtro por tipo de pessoa.
 *
 * Quem usa: `components/patterns/sidebar-body.tsx` (`navigationFor`, os
 * grupos da barra), `search-dialog.tsx` (`flattenNavigation`, a lista da
 * busca), `guest-header.tsx` (`guestActions`), `app-sidebar.tsx` (o tipo
 * `Viewer`) e `shell.tsx` (`viewerOf`). Os rótulos vêm de `pt.nav`, e os
 * ícones, do Lucide. SDD 14.5, 14.6 e 15.4.
 */
import {
  Activity,
  BadgeCheck,
  ClipboardList,
  FileText,
  Files,
  Headset,
  History,
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

/**
 * Um link da navegação. `end` deixa o `NavLink` ativo só no caminho exato:
 * sem ele, `/` e `/admin` ficariam ativos em toda página abaixo deles. As
 * Conversas (`/ask`) não têm `end` e ficam ativas também em `/ask/:id`.
 */
export type NavItem = {
  label: string
  to: string
  icon: LucideIcon
  end?: boolean
}

/** Um grupo rotulado da barra lateral (seção 14.5). */
export type NavGroup = {
  label: string
  items: NavItem[]
}

/**
 * Os quatro grupos da seção 15.4, na ordem da barra lateral: Assistente e
 * Conta para todos, Operação e Sistema só para o admin. A lista é
 * completa; `navigationFor` tira o que não cabe a cada pessoa.
 *
 * A seção 15.4 põe em Conta só Cadastrar ou Entrar, Conta e Privacidade.
 * O código também lista Termos de Uso e Novo aceite.
 */
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
    // Atendimento humano (seção 29.11): a fila para `attendant` e `admin`, e
    // os encerrados só para o admin.
    label: pt.nav.attendanceGroup,
    items: [
      {
        label: pt.nav.attendanceQueue,
        to: "/attendance",
        icon: Headset,
        end: true,
      },
      {
        label: pt.nav.attendanceClosed,
        to: "/admin/attendance",
        icon: History,
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
      {
        label: pt.nav.documents,
        to: "/admin/documents",
        icon: Files,
        end: true,
      },
      {
        label: pt.nav.quality,
        to: "/admin/quality",
        icon: Activity,
        end: true,
      },
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

/**
 * Quem está vendo o app. `guest` é o visitante sem sessão, e `attendant`, a
 * pessoa da equipe de atendimento (seção 29.3). SDD 14.5.
 */
export type Viewer = "guest" | "member" | "attendant" | "admin"

// Cadastro e entrada somem da navegação de quem já entrou (seção 14.5).
const guestOnly = new Set<string>(["/register", "/register/form", "/sign-in"])
// Os grupos só do admin, achados pelo rótulo.
const adminGroups = new Set<string>([pt.nav.operations, pt.nav.system])
// O grupo da equipe e o que só o admin vê dentro dele (seção 29.11).
const staffGroup = pt.nav.attendanceGroup
const adminOnly = new Set<string>(["/admin/attendance"])
// O `attendant` vê só os grupos Atendimento e Conta (seção 29.11).
const attendantGroups = new Set<string>([
  pt.nav.attendanceGroup,
  pt.nav.account,
])

/**
 * Traduz o `role` do `GET /v1/me` no tipo de pessoa. Sem perfil, é
 * visitante; qualquer papel que não seja `admin` conta como membro.
 */
export function viewerOf(role: string | null | undefined): Viewer {
  if (role === "admin") {
    return "admin"
  }
  if (role === "attendant") {
    return "attendant"
  }
  return role ? "member" : "guest"
}

/**
 * Grupos que fazem sentido para quem vê: sem cadastro e entrada para quem
 * já entrou, operação só para admin. Um grupo que fica vazio sai.
 *
 * Para o visitante, nenhum item sai: a busca ⌘K lista também `/account` e
 * `/legal/accept`, que levam ao login. A seção 14.5 pede que a busca do
 * visitante liste só as páginas públicas.
 */
export function navigationFor(viewer: Viewer): NavGroup[] {
  return navigation
    .filter((group) => viewer === "admin" || !adminGroups.has(group.label))
    .filter(
      (group) =>
        group.label !== staffGroup ||
        viewer === "admin" ||
        viewer === "attendant"
    )
    .filter(
      (group) => viewer !== "attendant" || attendantGroups.has(group.label)
    )
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) =>
          (viewer === "guest" || !guestOnly.has(item.to)) &&
          (viewer === "admin" || !adminOnly.has(item.to))
      ),
    }))
    .filter((group) => group.items.length > 0)
}

/**
 * Os itens de `navigationFor` sem os grupos: a lista que a busca ⌘K
 * (`search-dialog.tsx`) filtra pelo texto digitado.
 */
export function flattenNavigation(viewer: Viewer) {
  return navigationFor(viewer).flatMap((group) => group.items)
}

/**
 * Ações do cabeçalho de quem ainda não entrou (seção 14.5): Entrar, Criar
 * conta, que abre o formulário, e Cadastrar com IA, que abre a conversa.
 * O `GuestHeader` as mostra em linha e, no celular, no menu. `as const`
 * mantém cada `variant` como literal, no tipo que o `Button` aceita.
 */
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
