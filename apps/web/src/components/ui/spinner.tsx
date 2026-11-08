/**
 * Ícone de carregamento que gira (`Loader2Icon` do Lucide), do shadcn/ui.
 *
 * A seção 14.7 põe o spinner só dentro de botões, como Enviar, Salvar e
 * Sair. O selo de documento em processamento, em `/admin/documents`,
 * também o usa.
 *
 * O que o projeto mudou: com `aria-hidden`, o ícone fica decorativo, sem
 * papel nem nome, porque o texto do botão já diz "Enviando". Sem ele, o
 * ícone ganha `role="status"` e o nome "Carregando" de `pt.loading`, no
 * lugar do "Loading" do shadcn.
 *
 * O giro `animate-spin` é uma animação de CSS fora do catálogo da seção
 * 16.3, que só lista o Sonner e o Skeleton como exceções ao GSAP. Com
 * movimento reduzido, os estilos globais de `globals.css` o param.
 */
import { pt } from "@/i18n/pt.ts"
import { cn } from "cn"
import { Loader2Icon } from "lucide-react"

/**
 * Spinner de 16 px. Aceita `aria-hidden` como booleano ou como texto: o
 * JSX manda `true` quando o atributo vem sem valor, e algumas telas
 * escrevem `aria-hidden="true"`.
 */
function Spinner({
  className,
  "aria-label": ariaLabel,
  "aria-hidden": ariaHidden,
  ...props
}: React.ComponentProps<"svg">) {
  const hidden = ariaHidden === true || ariaHidden === "true"
  return (
    <Loader2Icon
      data-slot="spinner"
      role={hidden ? undefined : "status"}
      aria-label={hidden ? undefined : (ariaLabel ?? pt.loading)}
      aria-hidden={ariaHidden}
      className={cn("size-4 animate-spin", className)}
      {...props}
    />
  )
}

export { Spinner }
