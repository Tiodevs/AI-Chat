import type { HtmlTagDescriptor, Plugin } from "vite"

/**
 * Pede no `index.html`, com `modulepreload`, os arquivos das rotas que abrem `/`. Seção 5.3.
 *
 * As rotas carregam sob demanda (seção 13.1). Sem esta dica, o navegador só descobre o shell,
 * a moldura da rota e a página inicial depois de baixar e rodar o JavaScript de entrada, numa
 * segunda leva, e o LCP de `/` espera essa ida e volta a mais. Com ela, tudo vem na primeira
 * leva. Os arquivos continuam separados: uma rota que não é `/` só baixa a mais a página
 * inicial, que é pequena.
 */
export function preloadRoutes(modules: readonly string[]): Plugin {
  let base = "/"
  return {
    name: "atrium:preload-routes",
    apply: "build",
    configResolved(config) {
      base = config.base
    },
    transformIndexHtml: {
      order: "post",
      handler(html, context) {
        // O build do Storybook passa pelo mesmo Vite, com outro HTML: ele fica de fora.
        const bundle = context.bundle
        if (!bundle || context.path !== "/index.html") {
          return html
        }
        const files = new Set<string>()
        const visit = (fileName: string) => {
          const output = bundle[fileName]
          if (files.has(fileName) || output?.type !== "chunk") {
            return
          }
          files.add(fileName)
          output.imports.forEach(visit)
        }
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
