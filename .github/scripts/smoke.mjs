// Testes de fumaça de um ambiente publicado. Seções 13.4 e 22.3 do SDD, Etapa 10.1.
//
// Uso: node .github/scripts/smoke.mjs https://atrium-dev.vercel.app [commit] [https://api-na-railway]
//
// Tudo passa pela origem da Vercel, como no navegador: o rewrite leva /backend/* à API.
// Com o commit, a fumaça espera o /health da API responder com ele antes de testar. A Railway
// mantém a versão anterior no ar quando um deploy falha, e sem essa espera a fumaça poderia
// aprovar a versão antiga.
// Com a origem da API na Railway, a fumaça também confere que /v1 recusa o pedido direto, sem o
// segredo da borda, e que /health continua aberto para a Railway (seção 10.3, Etapa 12.5).
// Sai com código 1 se alguma verificação falhar, com a lista do que falhou.

const base = (process.argv[2] ?? "").replace(/\/+$/, "")
const expectedBuild = (process.argv[3] ?? "").trim()
const directApi = (process.argv[4] ?? "").trim().replace(/\/+$/, "")
if (!/^https?:\/\/[^/]+$/.test(base)) {
  console.error("Informe a origem do frontend, por exemplo https://atrium-dev.vercel.app")
  process.exit(2)
}
if (directApi && !/^https:\/\/[^/]+$/.test(directApi)) {
  console.error("A origem da API na Railway precisa ser https e sem caminho.")
  process.exit(2)
}

const requestTimeoutMs = 30_000
const failures = []

function check(condition, message) {
  if (!condition) {
    failures.push(message)
    console.error(`FALHOU  ${message}`)
  } else {
    console.log(`ok      ${message}`)
  }
}

function get(path, init = {}) {
  return fetch(`${base}${path}`, {
    redirect: "manual",
    ...init,
    signal: AbortSignal.timeout(requestTimeoutMs),
  })
}

async function json(response) {
  try {
    return await response.json()
  } catch {
    return null
  }
}

/** Espera um 200 que passe em `accept`. Devolve a última resposta ou o último erro. */
async function waitFor(path, { attempts, delayMs, accept = () => true }) {
  let last = null
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await get(path)
      last = response
      if (response.status === 200 && (await accept(response.clone()))) {
        return response
      }
    } catch (error) {
      last = error
    }
    await new Promise((resolve) => setTimeout(resolve, delayMs))
  }
  return last
}

// 1. A API responde pelo rewrite, com o commit esperado quando ele é informado.
const health = await waitFor("/backend/health", {
  attempts: expectedBuild ? 60 : 20,
  delayMs: expectedBuild ? 10_000 : 6_000,
  accept: async (response) => !expectedBuild || (await json(response))?.build === expectedBuild,
})
check(health instanceof Response && health.status === 200, "GET /backend/health responde 200")
if (health instanceof Response) {
  check(Boolean(health.headers.get("x-request-id")), "/backend/health devolve x-request-id")
  if (expectedBuild) {
    const body = await json(health)
    check(
      body?.build === expectedBuild,
      `a API no ar é a do commit ${expectedBuild} (respondeu ${body?.build ?? "sem commit"})`,
    )
  }
}
const ready = await waitFor("/backend/ready", { attempts: 20, delayMs: 6_000 })
check(ready instanceof Response && ready.status === 200, "GET /backend/ready responde 200")

// 2. Um endpoint de /v1 com no-store, que não fica no cache da Vercel (CA-3).
const first = await get("/backend/v1/legal/versions")
const versions = await json(first)
check(first.status === 200, "GET /backend/v1/legal/versions responde 200")
check(
  Boolean(versions?.terms) && Boolean(versions?.privacy_notice),
  "as versões dos Termos e do Aviso vêm no corpo",
)
check(
  (first.headers.get("cache-control") ?? "").includes("no-store"),
  "/backend/v1 sai com Cache-Control: no-store",
)
const second = await get("/backend/v1/legal/versions")
check(
  (second.headers.get("x-vercel-cache") ?? "").toUpperCase() !== "HIT",
  "a segunda leitura de /backend/v1 não vem do cache da Vercel",
)

// 3. A página e os cabeçalhos de segurança da seção 13.4 (CA-4).
const page = await get("/")
const html = await page.text()
check(page.status === 200 && html.includes('id="root"'), "GET / devolve a SPA")
const csp = page.headers.get("content-security-policy") ?? ""
check(csp.includes("default-src 'self'"), "Content-Security-Policy com default-src 'self'")
check(csp.includes("frame-ancestors 'none'"), "Content-Security-Policy com frame-ancestors 'none'")
check(page.headers.get("x-content-type-options") === "nosniff", "X-Content-Type-Options: nosniff")
check(
  page.headers.get("referrer-policy") === "strict-origin-when-cross-origin",
  "Referrer-Policy: strict-origin-when-cross-origin",
)
check(
  (page.headers.get("permissions-policy") ?? "").includes("camera=()"),
  "Permissions-Policy sem câmera, microfone e geolocalização",
)
const deepLink = await get("/privacy")
check(deepLink.status === 200, "uma rota da SPA, como /privacy, cai no index.html")
const missingAsset = await get("/assets/nao-existe.js")
check(missingAsset.status === 404, "um arquivo ausente em /assets responde 404, não o index.html")

// 4. O SSE atravessa o rewrite sem acumular: o primeiro tick chega antes do fim (CA-2).
const started = Date.now()
let firstTickAt = null
let ticks = 0
let streamStatus = 0
try {
  const stream = await get("/backend/v1/diagnostics/stream", {
    headers: { Accept: "text/event-stream" },
  })
  streamStatus = stream.status
  if (stream.status === 200 && stream.body) {
    const decoder = new TextDecoder()
    let buffer = ""
    for await (const chunk of stream.body) {
      buffer += decoder.decode(chunk, { stream: true })
      const found = buffer.match(/event: tick/g)?.length ?? 0
      if (found > 0 && firstTickAt === null) {
        firstTickAt = Date.now()
      }
      ticks = found
    }
  }
} catch (error) {
  console.error(`O fluxo de diagnóstico falhou: ${String(error)}`)
}
const endedAt = Date.now()
check(streamStatus === 200, "GET /backend/v1/diagnostics/stream responde 200")
check(ticks === 3, `o fluxo de diagnóstico traz 3 eventos tick (vieram ${ticks})`)
check(
  firstTickAt !== null && endedAt - firstTickAt >= 1000,
  `o primeiro tick chegou ${firstTickAt === null ? "nunca" : `${firstTickAt - started} ms`} depois do início e ${firstTickAt === null ? "-" : `${endedAt - firstTickAt} ms`} antes do fim`,
)

// 5. Direto na Railway: /v1 recusa o pedido sem o segredo da borda, e /health continua aberto.
if (directApi) {
  const direct = await fetch(`${directApi}/v1/conversations`, {
    redirect: "manual",
    signal: AbortSignal.timeout(requestTimeoutMs),
  })
  const directBody = await json(direct)
  check(
    direct.status === 403 && directBody?.error?.code === "forbidden",
    `GET /v1/conversations direto na Railway, sem o segredo da borda, responde 403 (respondeu ${direct.status})`,
  )
  const directHealth = await fetch(`${directApi}/health`, {
    redirect: "manual",
    signal: AbortSignal.timeout(requestTimeoutMs),
  })
  check(directHealth.status === 200, "GET /health direto na Railway responde 200")
}

if (failures.length > 0) {
  console.error(`\n${failures.length} verificação(ões) falharam em ${base}.`)
  process.exit(1)
}
console.log(`\nFumaça verde em ${base}.`)
