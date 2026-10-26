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

function itemClass(collapsed: boolean, active = false) {
  return cn(
    "flex items-center rounded-nav text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground",
    collapsed
      ? "size-8 justify-center"
      : "h-8 w-full min-w-0 gap-2 px-2.5",
    active && "bg-card text-foreground hover:bg-card hover:text-foreground",
  )
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
      aria-label={item.label}
      onClick={onNavigate}
      className={({ isActive }) => itemClass(collapsed, isActive)}
    >
      <Icon className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
      <span data-sidebar-label className={cn("truncate", collapsed && "sr-only")}>
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
    <div
      className={cn(
        "flex h-full min-h-0 w-full flex-col",
        collapsed ? "items-center gap-5" : "gap-3",
      )}
    >
      <div
        className={cn(
          "flex items-center",
          collapsed ? "w-8 flex-col gap-5" : "gap-2",
        )}
      >
        <NavLink
          to="/"
          end
          aria-label={pt.appName}
          onClick={onNavigate}
          className={cn(
            "flex min-w-0 items-center rounded-nav text-sm font-medium text-foreground-strong",
            collapsed ? "size-8 justify-center" : "h-8 flex-1 gap-2 px-2.5",
          )}
        >
          <span
            aria-hidden="true"
            className="flex size-4 shrink-0 items-center justify-center rounded-md bg-primary text-[10px] leading-none font-medium text-primary-foreground"
          >
            A
          </span>
          <span data-sidebar-label className={cn("truncate", collapsed && "sr-only")}>
            {pt.appName}
          </span>
        </NavLink>
        {showCollapse && onToggle ? (
          <Button
            variant="ghost"
            size="icon"
            className="size-8 shrink-0"
            aria-expanded={!collapsed}
            aria-controls="app-sidebar"
            aria-label={collapsed ? pt.sidebar.expand : pt.sidebar.collapse}
            onClick={onToggle}
          >
            {collapsed ? (
              <PanelLeftOpen className="size-4" strokeWidth={1.75} />
            ) : (
              <PanelLeftClose className="size-4" strokeWidth={1.75} />
            )}
          </Button>
        ) : null}
      </div>

      <Button
        variant="outline"
        aria-keyshortcuts="Meta+K Control+K"
        onClick={onSearch}
        className={cn(
          collapsed
            ? "grid size-8 place-items-center p-0 px-0"
            : "h-8 w-full justify-start px-2.5",
        )}
      >
        <Search
          className="size-4"
          strokeWidth={1.75}
          data-icon={collapsed ? undefined : "inline-start"}
        />
        <span
          data-sidebar-label
          className={cn(
            "flex min-w-0 flex-1 items-center justify-between gap-2",
            collapsed && "sr-only",
          )}
        >
          <span className="truncate">{pt.sidebar.search}</span>
          <kbd className="font-mono text-caption text-subtle-foreground">
            {commandShortcutLabel()}
          </kbd>
        </span>
      </Button>

      <nav
        aria-label={pt.sidebar.label}
        data-sidebar-nav
        className={cn(
          "flex min-h-0 w-full flex-1 flex-col overflow-x-hidden overflow-y-auto",
          collapsed ? "scrollbar-none items-center gap-5" : "gap-5",
        )}
      >
        {navigation.map((group) => (
          <div
            key={group.label}
            className={cn(
              "flex flex-col",
              collapsed ? "items-center gap-5" : "gap-1",
            )}
          >
            <p
              data-sidebar-label
              className={cn(
                "px-2.5 text-label text-subtle-foreground",
                collapsed && "sr-only",
              )}
            >
              {group.label}
            </p>
            <ul className={cn("flex flex-col", collapsed ? "items-center gap-5" : "gap-1")}>
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

      <Separator className={collapsed ? "w-8" : "w-full"} />

      <div className={cn("flex w-full flex-col", collapsed ? "items-center" : "gap-3")}>
        <div className={cn("grid w-full", collapsed ? "grid-rows-[0fr]" : "grid-rows-[1fr]")}>
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
