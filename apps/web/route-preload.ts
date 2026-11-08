/**
 * Um plugin do Vite que põe no `index.html` do build a dica de
 * `modulepreload` para as rotas que abrem `/` (seções 5.3 e 13.1).
 *
 * `modulepreload` é um `<link>` no `<head>` que manda o navegador baixar um
 * módulo JavaScript antes de alguém importá-lo. Quem usa:
 * `vite.config.ts`, com a lista da casca, da moldura e da página inicial.
 * As medidas que motivaram o plugin estão em
 * `docs/acessibilidade-e-desempenho.md` (Etapa 9.1).
 */
import type { HtmlTagDescriptor, Plugin } from "vite"

/**
 * Pede no `index.html`, com `modulepreload`, os arquivos das rotas que abrem `/`. Seção 5.3.
 *
 * As rotas carregam sob demanda (seção 13.1). Sem esta dica, o navegador só descobre o shell,
 * a moldura da rota e a página inicial depois de baixar e rodar o JavaScript de entrada, numa
 * segunda leva, e o LCP de `/` espera essa ida e volta a mais. Com ela, tudo vem na primeira
 * leva. Os arquivos continuam separados: uma rota que não é `/` só baixa a mais a página
 * inicial, que é pequena.
 *
 * 1. Acha no bundle os arquivos gerados para os módulos da lista.
 * 2. Junta a eles os arquivos que cada um importa de forma estática.
 * 3. Devolve um `<link rel="modulepreload">` por arquivo que o HTML ainda
 *    não cita.
 *
 * @param modules Caminhos dos módulos a partir da pasta do app, como
 *   `src/app/shell.tsx`.
 * @throws Erro no build quando um módulo da lista não vira arquivo.
 */
export function preloadRoutes(modules: readonly string[]): Plugin {
  let base = "/"
  return {
    name: "atrium:preload-routes",
    // Só no `vite build`: em desenvolvimento, o Vite serve os módulos um a
    // um e não há bundle.
    apply: "build",
    // O prefixo público dos arquivos, `/` a menos que a configuração mude.
    configResolved(config) {
      base = config.base
    },
    transformIndexHtml: {
      // `post` roda depois das transformações do próprio Vite, quando o
      // bundle já existe em `context.bundle`.
      order: "post",
      handler(html, context) {
        // O build do Storybook passa pelo mesmo Vite, com outro HTML: ele fica de fora.
        const bundle = context.bundle
        if (!bundle || context.path !== "/index.html") {
          return html
        }
        // 2. Visita um arquivo e, de forma recursiva, os que ele importa de
        // forma estática. Os imports dinâmicos, como as outras rotas, ficam
        // de fora.
        const files = new Set<string>()
        const visit = (fileName: string) => {
          const output = bundle[fileName]
          if (files.has(fileName) || output?.type !== "chunk") {
            return
          }
          files.add(fileName)
          output.imports.forEach(visit)
        }
        // 1. `facadeModuleId` é o módulo que um arquivo representa. A troca
        // de barras iguala os caminhos do Windows aos da lista.
        const found = new Set<string>()
        for (const output of Object.values(bundle)) {
          const id = output.type === "chunk" ? output.facadeModuleId?.replaceAll("\\", "/") : undefined
          const module = id ? modules.find((candidate) => id.endsWith(candidate)) : undefined
          if (output.type === "chunk" && module) {
            found.add(module)
            visit(output.fileName)
          }
        }
        const missing = modules.filter((module) => !found.has(module))
        if (missing.length > 0) {
          // Uma rota renomeada sem atualizar a lista tiraria a dica em silêncio.
          throw new Error(`preloadRoutes: rota sem arquivo no build: ${missing.join(", ")}`)
        }
        // 3. Fica de fora o que o HTML já cita, como o arquivo de entrada e
        // os que ele importa. Os atributos são os dos `modulepreload` que o
        // próprio Vite escreve.
        return [...files]
          .filter((fileName) => !html.includes(fileName))
          .map(
            (fileName): HtmlTagDescriptor => ({
              tag: "link",
              attrs: { rel: "modulepreload", crossorigin: true, href: `${base}${fileName}` },
              injectTo: "head",
            }),
          )
      },
    },
  }
}
