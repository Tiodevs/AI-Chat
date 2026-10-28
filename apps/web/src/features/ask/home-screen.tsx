import { useState } from "react"
import { Link } from "react-router"

import { Composer } from "@/components/patterns/composer.tsx"
import { SafetyNotice } from "@/components/patterns/safety-notice.tsx"
import { PageHeading } from "@/app/page-heading.tsx"
import { Button } from "@/components/ui/button.tsx"
import { pt } from "@/i18n/pt.ts"

import { SuggestionChips } from "./suggestion-chips.tsx"

export function HomeScreen({
  pending,
  error,
  budgetExceeded,
  onAsk,
}: {
  pending: boolean
  error: string | null
  budgetExceeded: boolean
  onAsk: (text: string) => void
}) {
  const [value, setValue] = useState("")

  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col gap-6">
      <PageHeading title={pt.home.title} variant="display" />
      <Composer
        value={value}
        onChange={setValue}
        onSubmit={() => {
          const text = value.trim()
          if (!text) {
            return
          }
          onAsk(text)
          setValue("")
        }}
        onStop={() => undefined}
        streaming={false}
        pending={pending}
        disabled={budgetExceeded}
        disabledReason={budgetExceeded ? pt.ask.unavailable : null}
        error={error}
      />
      <SuggestionChips disabled={budgetExceeded || pending} onSelect={onAsk} />
      <SafetyNotice />
      <div className="flex flex-wrap gap-4">
        <Button asChild variant="link" className="h-11 px-0 md:h-8">
          <Link to="/register">{pt.nav.register}</Link>
        </Button>
        <Button asChild variant="link" className="h-11 px-0 md:h-8">
          <Link to="/sign-in">{pt.nav.signIn}</Link>
        </Button>
      </div>
    </div>
  )
}
