// Testes de fumaça de um ambiente publicado. Seções 13.4 e 22.3 do SDD, Etapa 10.1.
//
// Uso: node .github/scripts/smoke.mjs https://atrium-dev.vercel.app
//
// Tudo passa pela origem da Vercel, como no navegador: o rewrite leva /backend/* à API.
// Sai com código 1 na primeira falha, com a mensagem do que falhou.

const base = (process.argv[2] ?? "").replace(/\/+$/, "")
if (!/^https?:\/\/[^/]+$/.test(base)) {
  console.error("Informe a origem do frontend, por exemplo https://atrium-dev.vercel.app")
  process.exit(2)
}

const failures = []

function check(condition, message) {
  if (!condition) {
    failures.push(message)
    console.error(`FALHOU  ${message}`)
  } else {
    console.log(`ok      ${message}`)
  }
}

async function waitFor(path, attempts = 20, delayMs = 6000) {
  let last = null
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      last = await fetch(`${base}${path}`, { redirect: "manual" })
      if (last.status === 200) {
        return last
      }
    } catch (error) {
      last = error
    }
    await new Promise((resolve) => setTimeout(resolve, delayMs))
  }
  return last
}

async function json(response) {
  try {
    return await response.json()
  } catch {
    return null
  }
}

// 1. A API responde pelo rewrite. O /ready confere banco, extensão vector e dimensão.
const health = await waitFor("/backend/health")
check(health instanceof Response && health.status === 200, "GET /backend/health responde 200")
if (health instanceof Response) {
  check(Boolean(health.headers.get("x-request-id")), "/backend/health devolve x-request-id")
}
const ready = await waitFor("/backend/ready")
check(ready instanceof Response && ready.status === 200, "GET /backend/ready responde 200")

// 2. Um endpoint de /v1 com no-store, que não fica no cache da Vercel (CA-3).
const first = await fetch(`${base}/backend/v1/legal/versions`)
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
const second = await fetch(`${base}/backend/v1/legal/versions`)
check(
  (second.headers.get("x-vercel-cache") ?? "").toUpperCase() !== "HIT",
  "a segunda leitura de /backend/v1 não vem do cache da Vercel",
)

// 3. A página e os cabeçalhos de segurança da seção 13.4 (CA-4).
const page = await fetch(`${base}/`)
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
const deepLink = await fetch(`${base}/privacy`)
check(deepLink.status === 200, "uma rota da SPA, como /privacy, cai no index.html")

// 4. O SSE atravessa o rewrite sem acumular: o primeiro tick chega antes do fim (CA-2).
const started = Date.now()
const stream = await fetch(`${base}/backend/v1/diagnostics/stream`, {
  headers: { Accept: "text/event-stream" },
})
check(stream.status === 200, "GET /backend/v1/diagnostics/stream responde 200")
let firstTickAt = null
let ticks = 0
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
const endedAt = Date.now()
check(ticks === 3, `o fluxo de diagnóstico traz 3 eventos tick (vieram ${ticks})`)
check(
  firstTickAt !== null && endedAt - firstTickAt >= 1000,
  `o primeiro tick chegou ${firstTickAt === null ? "nunca" : `${firstTickAt - started} ms`} depois do início e ${firstTickAt === null ? "-" : `${endedAt - firstTickAt} ms`} antes do fim`,
)

if (failures.length > 0) {
  console.error(`\n${failures.length} verificação(ões) falharam em ${base}.`)
  process.exit(1)
}
console.log(`\nFumaça verde em ${base}.`)
