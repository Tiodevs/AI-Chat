/**
 * Botão de perfil no rodapé da barra lateral, como o Customizer da imagem
 * de referência (seção 14.6): o primeiro nome de quem entrou e um menu com
 * Conta, Sair e a preferência de movimento.
 *
 * Aparece no `SidebarBody`, no desktop e no celular. A casca passa o nome
 * e o `onSignOut`, que chama `POST /v1/auth/logout` pelo `useSignOut`. Se
 * a saída falhar, a sessão continua e o erro aparece abaixo do botão, com
 * `role="alert"`.
 *
 * A preferência de movimento (Sistema, Reduzir movimento e Animar) é um
 * grupo de rádio do menu ligado ao `MotionProvider`: mudar a escolha
 * grava no `localStorage` e chama `gsap.matchMediaRefresh()` (seção
 * 16.4).
 *
 * Acessibilidade: o nome do botão é "Ana, menu da conta", que começa pelo
 * texto visível (WCAG 2.5.3). Recolhida, o rótulo fica em `sr-only` e o
 * ícone leva `data-flip-id` para a M13. Itens do menu com 44 px no
 * celular (seção 15.8).
 */
import { LogOut, UserRound } from "lucide-react"
import { useNavigate } from "react-router"

import { Button } from "@/components/ui/button.tsx"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu.tsx"
import { pt } from "@/i18n/pt.ts"
import { useMotion, type MotionPreference } from "@/motion/MotionProvider.tsx"
import { cn } from "@/lib/utils.ts"

// `on` liga a redução de movimento, e `off` a desliga; `system` segue o
// `prefers-reduced-motion` do aparelho.
const preferences: Array<{ value: MotionPreference; label: string }> = [
  { value: "system", label: pt.profile.motionSystem },
  { value: "on", label: pt.profile.motionReduce },
  { value: "off", label: pt.profile.motionAllow },
]

/** O que a casca sabe da conta: o nome e a saída, com o estado dela. */
export type ProfileAccount = {
  name: string | null
  onSignOut: () => void
  signingOut: boolean
  signOutError: string | null
}

/** Botão com o nome e o menu da conta. */
export function ProfileButton({
  collapsed,
  defaultOpen = false,
  name = null,
  onSignOut,
  signingOut = false,
  signOutError = null,
}: {
  collapsed: boolean
  /** Abre o menu já montado; só as histórias usam. */
  defaultOpen?: boolean
  /** Nome de quem entrou. Sem ele, o botão mostra "Visitante". */
  name?: string | null
  /** Com sessão, o menu oferece Sair no lugar de Entrar. */
  onSignOut?: () => void
  signingOut?: boolean
  signOutError?: string | null
}) {
  const navigate = useNavigate()
  const { preference, setPreference } = useMotion()

  return (
    <div className={cn("flex w-full flex-col gap-1", collapsed && "items-center")}>
    <DropdownMenu defaultOpen={defaultOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          aria-label={pt.profile.menuLabel.replace("{name}", name ?? pt.profile.guest)}
          className={cn(
            collapsed
              ? "grid size-8 place-items-center p-0 px-0"
              : "h-11 md:h-8 w-full justify-start px-2.5",
          )}
        >
          <UserRound
            className="size-4"
            strokeWidth={1.75}
            data-icon={collapsed ? undefined : "inline-start"}
            data-flip-id="profile"
          />
          <span data-sidebar-label className={cn("truncate", collapsed && "sr-only")}>
            {name ?? pt.profile.guest}
          </span>
        </Button>
      </DropdownMenuTrigger>
      {/* Recolhida, o menu abre à direita do ícone; expandida, acima. */}
      <DropdownMenuContent
        side={collapsed ? "right" : "top"}
        align="start"
        className="min-w-56"
      >
        <DropdownMenuGroup>
          {/* Conta e, com sessão, Sair; sem sessão, Entrar no lugar. */}
          <DropdownMenuItem
            className="min-h-11 md:min-h-8"
            onSelect={() => {
              navigate("/account")
            }}
          >
            {pt.nav.accountPage}
          </DropdownMenuItem>
          {onSignOut ? (
            <DropdownMenuItem
              className="min-h-11 md:min-h-8"
              disabled={signingOut}
              onSelect={() => {
                onSignOut()
              }}
            >
              <LogOut strokeWidth={1.75} aria-hidden="true" />
              {signingOut ? pt.profile.signingOut : pt.profile.signOut}
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem
              className="min-h-11 md:min-h-8"
              onSelect={() => {
                navigate("/sign-in")
              }}
            >
              {pt.nav.signIn}
            </DropdownMenuItem>
          )}
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>{pt.profile.motion}</DropdownMenuLabel>
        {/* O Radix entrega o valor como texto; a guarda o estreita para */}
        {/* `MotionPreference` antes de gravar. */}
        <DropdownMenuRadioGroup
          value={preference}
          onValueChange={(value) => {
            if (value === "system" || value === "on" || value === "off") {
              setPreference(value)
            }
          }}
        >
          {preferences.map((item) => (
            <DropdownMenuRadioItem
              key={item.value}
              value={item.value}
              className="min-h-11 md:min-h-8"
            >
              {item.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
    {/* Com a barra recolhida, o erro de saída não aparece. */}
    {signOutError && !collapsed ? (
      <p role="alert" className="px-2.5 text-caption text-danger">
        {signOutError}
      </p>
    ) : null}
    </div>
  )
}
