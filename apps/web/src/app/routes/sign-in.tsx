/**
 * Rota `/sign-in`: e-mail, senha e o link para o cadastro (seção 15.5).
 *
 * É a única rota que monta a própria marcação, sem uma tela de `features`:
 * o título, um `Card` e o `SignInForm`. O controller `useSignIn` faz o
 * login e volta para o `returnTo` que os guards de `guards.ts` puseram na
 * URL.
 */
import { PageHeading } from "@/app/page-heading.tsx"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx"
import { SignInForm } from "@/features/auth/sign-in-form.tsx"
import { useSignIn } from "@/features/auth/useSignIn.ts"
import { pt } from "@/i18n/pt.ts"

/** A página de entrar, numa coluna de até 448 px (`max-w-md`). */
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
