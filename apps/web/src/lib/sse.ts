export type ServerEvent = {
  event: string
  data: string
}

export function takeEvents(buffer: string): {
  events: ServerEvent[]
  rest: string
} {
  const normalized = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n")
  const frames = normalized.split("\n\n")
  const rest = frames.pop() ?? ""
  const events: ServerEvent[] = []
  for (const frame of frames) {
    const event = parseFrame(frame)
    if (event) {
      events.push(event)
    }
  }
  return { events, rest }
}

export async function* readEventStream(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<ServerEvent> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let rest = ""
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        rest += decoder.decode()
        if (rest.trim()) {
          const flushed = takeEvents(`${rest}\n\n`)
          for (const event of flushed.events) {
            yield event
          }
        }
        return
      }
      rest += decoder.decode(value, { stream: true })
      const taken = takeEvents(rest)
      rest = taken.rest
      for (const event of taken.events) {
        yield event
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export function postEventStream(
  url: string,
  body: unknown,
  signal: AbortSignal
): Promise<Response> {
  return fetch(url, {
    method: "POST",
    credentials: "include",
    headers: {
      "content-type": "application/json",
      accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal,
  })
}

function parseFrame(frame: string): ServerEvent | null {
  let event = "message"
  const data: string[] = []
  let sawData = false
  for (const line of frame.split("\n")) {
    if (line === "" || line.startsWith(":")) {
      continue
    }
    const colon = line.indexOf(":")
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? "" : line.slice(colon + 1)
    if (value.startsWith(" ")) {
      value = value.slice(1)
    }
    if (field === "event") {
      event = value
    } else if (field === "data") {
      data.push(value)
      sawData = true
    }
  }
  if (!sawData) {
    return null
  }
  return { event, data: data.join("\n") }
}
