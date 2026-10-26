import { useRef, useState } from "react"
import { Link } from "react-router"

import { flattenNavigation } from "@/app/navigation.ts"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.tsx"
import { Input } from "@/components/ui/input.tsx"
import { pt } from "@/i18n/pt.ts"
import { useGsapPresence } from "@/motion/useGsapPresence.ts"

export function SearchDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  const mounted = useGsapPresence(open, panelRef)
  const [query, setQuery] = useState("")
  const [previousOpen, setPreviousOpen] = useState(open)
  if (open !== previousOpen) {
    setPreviousOpen(open)
    if (open) {
      setQuery("")
    }
  }
  const normalized = query.trim().toLocaleLowerCase("pt-BR")
  const items = flattenNavigation().filter((item) =>
    item.label.toLocaleLowerCase("pt-BR").includes(normalized),
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {mounted ? (
        <DialogContent forceMount className="sm:max-w-md">
          <div ref={panelRef} className="flex flex-col gap-4">
            <DialogHeader>
              <DialogTitle className="text-title">
                {pt.sidebar.search}
              </DialogTitle>
              <DialogDescription>
                {pt.sidebar.searchDescription}
              </DialogDescription>
            </DialogHeader>
            <Input
              autoFocus
              value={query}
              aria-label={pt.sidebar.search}
              placeholder={pt.sidebar.searchPlaceholder}
              className="min-h-11"
              onChange={(event) => {
                setQuery(event.target.value)
              }}
            />
            {items.length === 0 ? (
              <p className="text-body text-muted-foreground">
                {pt.sidebar.searchEmpty}
              </p>
            ) : (
              <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto">
                {items.map((item) => (
                  <li key={item.to}>
                    <Link
                      to={item.to}
                      className="flex min-h-11 items-center rounded-nav px-3 text-body text-foreground hover:bg-muted"
                      onClick={() => {
                        onOpenChange(false)
                      }}
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </DialogContent>
      ) : null}
    </Dialog>
  )
}
