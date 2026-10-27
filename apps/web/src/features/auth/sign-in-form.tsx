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

type SignInValues = z.infer<typeof signInSchema>

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
