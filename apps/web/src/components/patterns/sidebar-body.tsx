import { PanelLeftClose, PanelLeftOpen, Search } from "lucide-react"
import { NavLink } from "react-router"

import { ProfileButton } from "@/components/patterns/profile-button.tsx"
import { SidebarNoticeCard } from "@/components/patterns/sidebar-notice-card.tsx"
import { Button } from "@/components/ui/button.tsx"
import { Separator } from "@/components/ui/separator.tsx"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip.tsx"
import { navigation, type NavItem } from "@/app/navigation.ts"
import { pt } from "@/i18n/pt.ts"
import { cn } from "@/lib/utils.ts"

function commandShortcutLabel() {
  if (typeof navigator === "undefined") {
    return "⌘K"
  }
  return /Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘K" : "Ctrl+K"
}

function SidebarLink({
  item,
  collapsed,
  onNavigate,
}: {
  item: NavItem
  collapsed: boolean
  onNavigate?: () => void
}) {
  const Icon = item.icon
  const link = (
    <NavLink
      to={item.to}
      end={item.end ?? false}
      data-flip
      aria-label={item.label}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "flex min-h-11 items-center gap-3 rounded-nav px-3 text-body md:min-h-8",
          collapsed && "justify-center px-0",
          isActive
            ? "bg-card text-foreground"
            : "text-muted-foreground hover:bg-muted hover:text-foreground",
        )
      }
    >
      <Icon strokeWidth={1.75} aria-hidden="true" />
      <span data-sidebar-label className="truncate">
        {item.label}
      </span>
    </NavLink>
  )

  if (!collapsed) {
    return link
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{item.label}</TooltipContent>
    </Tooltip>
  )
}

export function SidebarBody({
  collapsed,
  onSearch,
  onNavigate,
  onToggle,
  showCollapse = false,
}: {
  collapsed: boolean
  onSearch: () => void
  onNavigate?: () => void
  onToggle?: () => void
  showCollapse?: boolean
}) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div
        data-flip
        className={cn("flex items-center gap-2", collapsed && "flex-col")}
      >
        <NavLink
          to="/"
          end
          aria-label={pt.appName}
          onClick={onNavigate}
          className={cn(
            "flex min-h-11 min-w-0 items-center gap-3 rounded-nav px-2 text-foreground-strong md:min-h-8",
            collapsed ? "justify-center px-0" : "flex-1",
          )}
        >
          <span
            aria-hidden="true"
            className="flex size-6 shrink-0 items-center justify-center rounded-md bg-primary text-caption text-primary-foreground"
          >
            A
          </span>
          <span data-sidebar-label className="truncate text-label">
            {pt.appName}
          </span>
        </NavLink>
        {showCollapse && onToggle ? (
          <Button
            variant="ghost"
            size="icon"
            className="size-11 shrink-0 md:size-8"
            aria-expanded={!collapsed}
            aria-controls="app-sidebar"
            aria-label={collapsed ? pt.sidebar.expand : pt.sidebar.collapse}
            onClick={onToggle}
          >
            {collapsed ? (
              <PanelLeftOpen strokeWidth={1.75} />
            ) : (
              <PanelLeftClose strokeWidth={1.75} />
            )}
          </Button>
        ) : null}
      </div>

      <Button
        variant="outline"
        data-flip
        aria-keyshortcuts="Meta+K Control+K"
        onClick={onSearch}
        className={cn(
          "w-full min-h-11 justify-start gap-3 px-3 md:min-h-8",
          collapsed && "justify-center px-0",
        )}
      >
        <Search strokeWidth={1.75} data-icon="inline-start" />
        <span
          data-sidebar-label
          className="flex min-w-0 flex-1 items-center justify-between gap-2"
        >
          <span className="truncate">{pt.sidebar.search}</span>
          <kbd className="font-mono text-caption text-subtle-foreground">
            {commandShortcutLabel()}
          </kbd>
        </span>
      </Button>

      <nav aria-label={pt.sidebar.label} className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto">
        {navigation.map((group) => (
          <div key={group.label} className="flex flex-col gap-1">
            <p
              data-sidebar-label
              className="px-3 text-label text-subtle-foreground"
            >
              {group.label}
            </p>
            <ul className="flex flex-col gap-1">
              {group.items.map((item) => (
                <li key={item.to}>
                  <SidebarLink
                    item={item}
                    collapsed={collapsed}
                    onNavigate={onNavigate}
                  />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <Separator />

      <div className="flex flex-col gap-3">
        <div
          className={cn(
            "grid",
            collapsed ? "grid-rows-[0fr]" : "grid-rows-[1fr]",
          )}
        >
          <div
            className="min-h-0 overflow-hidden"
            inert={collapsed ? true : undefined}
            aria-hidden={collapsed}
          >
            <SidebarNoticeCard />
          </div>
        </div>
        <ProfileButton collapsed={collapsed} />
      </div>
    </div>
  )
}
