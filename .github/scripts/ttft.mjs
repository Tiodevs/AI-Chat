// Tempo até o primeiro token e tempo total da resposta, medidos no cliente. Seção 5.3 e
// Etapa 9.1, CA-4.
//
// Uso: node .github/scripts/ttft.mjs https://atrium-gold.vercel.app [perguntas]
//
// Precisa da API com a chave do Gemini e o corpus semeado. Uma pergunta de aquecimento roda
// antes e fica fora da conta, porque a meta vale com a API aquecida. O padrão são 20 perguntas,
// abaixo do limite de 30 por hora do convidado (seção 10.4). Mede pela origem da Vercel, como
// o navegador; o Grafana mostra o mesmo sinal do lado da API em atrium_qa_first_token_seconds.
//
// Quem usa: quem opera, à mão. Não roda em nenhum workflow. A Etapa 12.4 registrou com ele o
// p95 antes e depois da mudança. Todas as perguntas vão na mesma conversa, então o histórico
// enviado ao modelo cresce até a janela da seção 7.1. Sai com 0 quando os dois p95 cumprem a
// seção 5.3, com 1 quando um deles não cumpre ou não há o que medir, e com 2 para argumentos
// inválidos.

import { randomUUID } from "node:crypto"

const base = (process.argv[2] ?? "").replace(/\/+$/, "")
const total = Number(process.argv[3] ?? "20")
// No máximo 29: com a pergunta de aquecimento, são 30 pedidos, o limite por hora da chave de
// convidado.
if (!/^https?:\/\/[^/]+$/.test(base) || !Number.isInteger(total) || total < 1 || total > 29) {
  console.error("Uso: node .github/scripts/ttft.mjs https://<frontend> [1 a 29 perguntas]")
  process.exit(2)
}

// As quatro perguntas que esperam `answered` no conjunto de avaliação (seção 21.2), em rodízio.
const questions = [
  "Qual é o horário de visita?",
  "Onde posso estacionar?",
  "Quantas pessoas podem visitar a UTI ao mesmo tempo?",
  "Qual telefone eu ligo sobre uma cobrança?",
]
// Um POST precisa de `Origin` igual ao WEB_ORIGIN da API (NFR-12), que é a própria origem
// da Vercel.
const headers = { Origin: base, "Content-Type": "application/json" }

// Uma conversa de convidado. O `fetch` do Node não guarda cookies, então o `atrium_guest` da
// resposta segue à mão em cada pergunta.
const created = await fetch(`${base}/backend/v1/conversations`, {
  method: "POST",
  headers,
  signal: AbortSignal.timeout(30_000),
})
if (created.status !== 201) {
  console.error(`Não foi possível criar a conversa: HTTP ${created.status}`)
  process.exit(1)
}
const conversation = (await created.json()).id
const guest = (created.headers.get("set-cookie") ?? "").match(/atrium_guest=([^;]+)/)?.[1]
if (!guest) {
  console.error("A API não devolveu o cookie de convidado.")
  process.exit(1)
}

/**
 * Faz uma pergunta e lê o fluxo SSE até o fim.
 *
 * Devolve `{ ok: false, status }` quando o envio não responde 200, ou `ok`, o primeiro token e
 * o total em milissegundos, contados do envio, e o desfecho do evento `done`. Cada pergunta
 * leva um `client_message_id` novo, a chave de idempotência da seção 7.1.
 */
async function ask(text) {
  const started = performance.now()
  // O prazo de 150 s fica acima dos 120 s de tempo limite do gerador (seção 5.3).
  const response = await fetch(`${base}/backend/v1/conversations/${conversation}/messages`, {
    method: "POST",
    headers: { ...headers, Cookie: `atrium_guest=${guest}` },
    body: JSON.stringify({ text, client_message_id: randomUUID() }),
    signal: AbortSignal.timeout(150_000),
  })
  if (response.status !== 200 || !response.body) {
    return { ok: false, status: response.status }
  }
  const decoder = new TextDecoder()
  let buffer = ""
  let firstToken = null
  for await (const chunk of response.body) {
    buffer += decoder.decode(chunk, { stream: true })
    if (firstToken === null && buffer.includes("event: token")) {
      firstToken = performance.now() - started
    }
  }
  const outcome = buffer.match(/event: done\ndata: (\{.*\})/)?.[1]
  return {
    ok: true,
    firstToken,
    total: performance.now() - started,
    outcome: outcome ? JSON.parse(outcome).outcome : "sem done",
  }
}

/**
 * Percentil pelo posto mais próximo: o menor valor que deixa pelo menos `p`% das amostras
 * até ele. Uma lista vazia devolve `undefined`.
 */
function percentile(values, p) {
  const sorted = [...values].sort((left, right) => left - right)
  const index = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1)
  return sorted[Math.max(0, index)]
}

// Aquecimento, fora da conta.
await ask("Qual é o horário de visita?")
const firstTokens = []
const totals = []
const outcomes = {}
for (let index = 0; index < total; index += 1) {
  const result = await ask(questions[index % questions.length])
  if (!result.ok) {
    console.error(`Pergunta ${index + 1}: HTTP ${result.status}`)
    continue
  }
  outcomes[result.outcome] = (outcomes[result.outcome] ?? 0) + 1
  // Só a resposta gerada pelo modelo conta: a resposta fixa de indisponibilidade é imediata.
  if (result.outcome !== "answered") {
    continue
  }
  if (result.firstToken !== null) {
    firstTokens.push(result.firstToken)
  }
  totals.push(result.total)
}
if (totals.length === 0) {
  console.error(`Nenhuma resposta answered (${JSON.stringify(outcomes)}). Confira GEMINI_API_KEY e a semente.`)
  process.exit(1)
}

const seconds = (value) => (value === undefined ? "-" : `${(value / 1000).toFixed(2)} s`)
console.log(`Respostas answered medidas: ${totals.length} de ${total}. Desfechos: ${JSON.stringify(outcomes)}`)
console.log(`Primeiro token: p50 ${seconds(percentile(firstTokens, 50))}, p95 ${seconds(percentile(firstTokens, 95))} (meta p95 abaixo de 3 s)`)
console.log(`Resposta completa: p50 ${seconds(percentile(totals, 50))}, p95 ${seconds(percentile(totals, 95))} (meta p95 abaixo de 12 s)`)
const ttftOk = firstTokens.length > 0 && percentile(firstTokens, 95) < 3000
const totalOk = totals.length > 0 && percentile(totals, 95) < 12_000
process.exit(ttftOk && totalOk ? 0 : 1)
