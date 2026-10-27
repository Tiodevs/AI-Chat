import { pt } from "@/i18n/pt.ts"

export function safeReturnTo(value: string | null): string {
  if (
    value === null ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.startsWith("/\\") ||
    value.includes("\\") ||
    value.includes("://")
  ) {
    return "/"
  }
  return value
}

export function limitMessage(retryAfterSeconds: number): string {
  const minutes = Math.max(1, Math.ceil(retryAfterSeconds / 60))
  if (minutes === 1) {
    return pt.signIn.limitedOne
  }
  return pt.signIn.limitedMany.replace("{minutes}", String(minutes))
}
