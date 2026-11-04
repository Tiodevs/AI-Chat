import { Menu } from "lucide-react"
import { Link, NavLink, useNavigate } from "react-router"

import { guestActions } from "@/app/navigation.ts"
import { Button } from "@/components/ui/button.tsx"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu.tsx"
import { pt } from "@/i18n/pt.ts"

/** Cabeçalho de quem ainda não entrou: sem barra lateral, só entrar e criar conta. SDD 14.5. */
export function GuestHeader({ compact }: { compact: boolean }) {
  const navigate = useNavigate()

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-shell px-4 md:px-6">
      <Link
        to="/"
        className="flex min-h-11 items-center gap-2 rounded-nav text-sm font-medium text-foreground-strong md:min-h-8"
      >
        <span
          aria-hidden="true"
          className="flex size-6 shrink-0 items-center justify-center rounded-md bg-primary text-caption font-medium text-primary-foreground"
        >
          A
        </span>
        {pt.appName}
      </Link>
      {compact ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="min-h-11">
              <Menu strokeWidth={1.75} data-icon="inline-start" aria-hidden="true" />
              {pt.sidebar.guestMenu}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-56">
            {guestActions.map((action) => {
              const Icon = action.icon
              return (
                <DropdownMenuItem
                  key={action.to}
                  className="min-h-11"
                  onSelect={() => {
                    void navigate(action.to)
                  }}
                >
                  <Icon strokeWidth={1.75} aria-hidden="true" />
                  {action.label}
                </DropdownMenuItem>
              )
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        <nav aria-label={pt.sidebar.guestMenu}>
          <ul className="m-0 flex list-none items-center gap-2 p-0">
            {guestActions.map((action) => {
              const Icon = action.icon
              return (
                <li key={action.to}>
                  <Button asChild variant={action.variant} className="h-8">
                    <NavLink
                      to={action.to}
                      end
                      className={({ isActive }) =>
                        isActive ? "ring-1 ring-ring" : undefined
                      }
                    >
                      <Icon strokeWidth={1.75} data-icon="inline-start" aria-hidden="true" />
                      {action.label}
                    </NavLink>
                  </Button>
                </li>
              )
            })}
          </ul>
        </nav>
      )}
    </header>
  )
}
