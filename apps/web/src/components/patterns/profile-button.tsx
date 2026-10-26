import { UserRound } from "lucide-react"
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

const preferences: Array<{ value: MotionPreference; label: string }> = [
  { value: "system", label: pt.profile.motionSystem },
  { value: "on", label: pt.profile.motionReduce },
  { value: "off", label: pt.profile.motionAllow },
]

export function ProfileButton({
  collapsed,
  defaultOpen = false,
}: {
  collapsed: boolean
  defaultOpen?: boolean
}) {
  const navigate = useNavigate()
  const { preference, setPreference } = useMotion()

  return (
    <DropdownMenu defaultOpen={defaultOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          aria-label={pt.profile.menu}
          className={cn(
            collapsed
              ? "grid size-8 place-items-center p-0 px-0"
              : "h-8 w-full justify-start px-2.5",
          )}
        >
          <UserRound
            className="size-4"
            strokeWidth={1.75}
            data-icon={collapsed ? undefined : "inline-start"}
          />
          <span data-sidebar-label className={cn("truncate", collapsed && "sr-only")}>
            {pt.profile.guest}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side={collapsed ? "right" : "top"}
        align="start"
        className="min-w-56"
      >
        <DropdownMenuGroup>
          <DropdownMenuItem
            className="min-h-11 md:min-h-8"
            onSelect={() => {
              navigate("/account")
            }}
          >
            {pt.nav.accountPage}
          </DropdownMenuItem>
          <DropdownMenuItem
            className="min-h-11 md:min-h-8"
            onSelect={() => {
              navigate("/sign-in")
            }}
          >
            {pt.nav.signIn}
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>{pt.profile.motion}</DropdownMenuLabel>
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
  )
}
