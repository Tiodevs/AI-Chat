/**
 * Bloco que pulsa no formato do conteúdo que ainda vai chegar, do
 * shadcn/ui. Um `div` com classes, sem Radix.
 *
 * A seção 14.7 pede skeleton no formato do conteúdo para todo
 * carregamento. Aparece na espera da resposta (`AssistantMessage`), nas
 * tabelas (`DataTable`) e nos cards do admin (`StatCard`), na conta, no
 * cadastro e na conversa.
 *
 * O projeto acrescentou `aria-hidden`: o leitor de tela não lê blocos
 * vazios. Quem avisa a espera é o contêiner, com `aria-busy` ou um texto
 * em `sr-only`, como o "Preparando a resposta" do `AssistantMessage`.
 *
 * O pulso `animate-pulse` é uma das duas exceções ao GSAP da seção 16.3.
 * Ele dura os 2 s padrão do Tailwind, e não um token da seção 16.2. Com
 * movimento reduzido, os estilos globais de `globals.css` o param.
 */
import { cn } from "cn"

/** Bloco de espera. Dê largura e altura pela `className`. */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden="true"
      className={cn("animate-pulse rounded-lg bg-muted", className)}
      {...props}
    />
  )
}

export { Skeleton }
