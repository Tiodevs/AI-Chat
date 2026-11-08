/**
 * Formulário da tela Entrar (`/sign-in`): e-mail, senha e o link para o
 * cadastro. Seção 15.5 do SDD (Entrar).
 *
 * View: `app/routes/sign-in.tsx` passa o `submit`, o `pending` e o erro de
 * `useSignIn`. Usa o react-hook-form com zod e os componentes `Field` do
 * shadcn/ui (seção 14.8).
 */
import { CircleAlert } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { Link } from "react-router"

import { Button } from "@/components/ui/button.tsx"
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field.tsx"
import { Input } from "@/components/ui/input.tsx"
import { Spinner } from "@/components/ui/spinner.tsx"
import { pt } from "@/i18n/pt.ts"

/**
 * Validação no navegador, só de presença e de formato, com as mensagens de
 * `pt.signIn`. Quem confere a senha é a API.
 */
const signInSchema = z.object({
  email: z
    .string()
    .trim()
    .superRefine((value, context) => {
      if (!value) {
        context.addIssue({ code: "custom", message: pt.signIn.emailRequired })
        return
      }
      if (!z.email().safeParse(value).success) {
        context.addIssue({ code: "custom", message: pt.signIn.emailInvalid })
      }
    }),
  password: z.string().min(1, pt.signIn.passwordRequired),
})

/** Valores do formulário, inferidos do esquema pelo `z.infer`. */
type SignInValues = z.infer<typeof signInSchema>

/**
 * Campos de e-mail e senha, o botão Entrar e o link Criar uma conta.
 *
 * O `zodResolver` faz o `handleSubmit` validar com o esquema antes de
 * chamar `onSubmit`. O `error` vem da API e não diz qual campo errou,
 * porque o login nunca revela se o e-mail existe (seção 10.4). Por isso ele
 * marca os dois campos como inválidos e os liga ao mesmo alerta, salvo
 * quando o campo tem um erro próprio do zod.
 */
export function SignInForm({
  pending,
  error,
  onSubmit,
}: {
  pending: boolean
  error: string | null
  onSubmit: (values: SignInValues) => Promise<void> | void
}) {
  const form = useForm<SignInValues>({
    resolver: zodResolver(signInSchema),
    defaultValues: { email: "", password: "" },
  })
  const emailError = form.formState.errors.email?.message
  const passwordError = form.formState.errors.password?.message

  return (
    <form
      className="flex flex-col gap-5"
      // Desliga a validação do navegador: valem as mensagens do zod.
      noValidate
      onSubmit={(event) => {
        void form.handleSubmit(onSubmit)(event)
      }}
    >
      <FieldGroup>
        <Field data-invalid={emailError || error ? true : undefined} data-disabled={pending || undefined}>
          <FieldLabel htmlFor="email">{pt.signIn.email}</FieldLabel>
          <Input
            id="email"
            type="email"
            // `username` e `current-password` deixam o gerenciador de
            // senhas preencher a conta salva.
            autoComplete="username"
            className="h-11 md:h-8"
            aria-invalid={Boolean(emailError || error)}
            aria-describedby={emailError ? "email-error" : error ? "sign-in-error" : undefined}
            disabled={pending}
            {...form.register("email")}
          />
          {emailError ? <FieldError id="email-error">{emailError}</FieldError> : null}
        </Field>
        <Field data-invalid={passwordError || error ? true : undefined} data-disabled={pending || undefined}>
          <FieldLabel htmlFor="password">{pt.signIn.password}</FieldLabel>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            className="h-11 md:h-8"
            aria-invalid={Boolean(passwordError || error)}
            aria-describedby={passwordError ? "password-error" : error ? "sign-in-error" : undefined}
            disabled={pending}
            {...form.register("password")}
          />
          {passwordError ? <FieldError id="password-error">{passwordError}</FieldError> : null}
        </Field>
      </FieldGroup>
      {error ? (
        <div id="sign-in-error" role="alert" className="flex items-start gap-2 text-body text-danger">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p>{error}</p>
        </div>
      ) : null}
      <Button type="submit" disabled={pending} className="h-11 w-full md:h-8">
        {pending ? <Spinner aria-hidden data-icon="inline-start" /> : null}
        {pending ? pt.signIn.pending : pt.signIn.submit}
      </Button>
      <Button asChild variant="link" className="h-11 w-fit px-0 md:h-8">
        <Link to="/register">{pt.signIn.register}</Link>
      </Button>
    </form>
  )
}
