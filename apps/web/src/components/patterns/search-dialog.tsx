/**
 * Busca do `⌘K`: um diálogo que filtra as páginas do Atrium pelo nome
 * (seções 14.5, 14.6 e 15.8).
 *
 * A casca (`app/shell.tsx`) o carrega sob demanda e o abre pelo atalho
 * `⌘K` ou `Ctrl+K` e pelo botão Buscar da barra lateral. A lista é a
 * mesma navegação de `flattenNavigation(viewer)`: sem sessão, só as
 * páginas públicas (seção 14.5).
 *
 * É o `CommandPalette` da seção 14.6, feito com `Dialog`, `Input` e links,
 * sem o `cmdk` da seção 13.1, que não está nas dependências. A seção 15.4
 * pede também as conversas recentes do membro, e a lista ainda não as
 * tem. Não há navegação por setas: o Tab percorre os links.
 *
 * Acessibilidade: o diálogo tem título e descrição, e o campo recebe o
 * foco ao abrir. Links de 44 px (seção 15.8).
 *
 * Movimento: M14 (seção 16.3). `forceMount` mantém o conteúdo, e o
 * `useGsapPresence` anima a caixa interna. A saída não roda, porque o hook
 * desmonta antes; a Etapa 14.3 do plano corrige o hook.
 */
import { useRef, useState } from "react"
import { Link } from "react-router"

import { flattenNavigation, type Viewer } from "@/app/navigation.ts"
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

/** O diálogo de busca, controlado pela casca. */
export function SearchDialog({
  open,
  onOpenChange,
  viewer = "guest",
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Quem vê: escolhe as páginas da lista. */
  viewer?: Viewer
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  const mounted = useGsapPresence(open, panelRef)
  const [query, setQuery] = useState("")
  // Limpa a busca a cada abertura. O React recomenda ajustar o estado
  // durante a renderização, comparando com a prop anterior, em vez de um
  // efeito que pintaria a busca velha por um quadro.
  const [previousOpen, setPreviousOpen] = useState(open)
  if (open !== previousOpen) {
    setPreviousOpen(open)
    if (open) {
      setQuery("")
    }
  }
  // Filtro por trecho do nome, sem diferença de maiúsculas no pt-BR.
  const normalized = query.trim().toLocaleLowerCase("pt-BR")
  const items = flattenNavigation(viewer).filter((item) =>
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
            {/* O nome "Buscar" vem do `aria-label`; o placeholder não é */}
            {/* rótulo. */}
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
                    {/* Escolher uma página navega e fecha o diálogo. */}
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
