import { PageHeading } from "@/app/page-heading.tsx"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx"
import { SignInForm } from "@/features/auth/sign-in-form.tsx"
import { useSignIn } from "@/features/auth/useSignIn.ts"
import { pt } from "@/i18n/pt.ts"

export function Component() {
  const { submit, pending, error } = useSignIn()
  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-6">
      <PageHeading title={pt.pages.signIn} />
      <Card>
        <CardHeader>
          <CardTitle>{pt.signIn.lead}</CardTitle>
        </CardHeader>
        <CardContent>
          <SignInForm pending={pending} error={error} onSubmit={submit} />
        </CardContent>
      </Card>
    </div>
  )
}
