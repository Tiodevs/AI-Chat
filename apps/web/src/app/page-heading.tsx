import { useEffect } from "react"

import { pt } from "@/i18n/pt.ts"

export function PageHeading({
  title,
  variant = "title",
}: {
  title: string
  variant?: "title" | "display"
}) {
  useEffect(() => {
    document.title = `${title} · ${pt.appName}`
  }, [title])

  return (
    <h1
      id="page-title"
      tabIndex={-1}
      className={
        variant === "display"
          ? "text-display text-foreground-strong"
          : "text-title text-foreground-strong"
      }
    >
      {title}
    </h1>
  )
}

export function focusPageTitle() {
  const heading = document.getElementById("page-title")
  if (!(heading instanceof HTMLElement)) {
    return
  }
  heading.focus({ preventScroll: true })
}
