import { describe, expect, it } from "vitest"

import { pt } from "@/i18n/pt.ts"

import {
  consentIssues,
  emailOffersSignIn,
  emptyConsents,
  formValuesFromFields,
  passwordStrength,
  phaseForStep,
  phaseScale,
  registrationFormSchema,
  toFormPayload,
} from "./model.ts"

describe("cadastro", () => {
  it("mapeia o passo da máquina para a etapa visível", () => {
    expect(phaseForStep("full_name")).toBe("details")
    expect(phaseForStep("phone")).toBe("details")
    expect(phaseForStep("password")).toBe("password")
    expect(phaseForStep("review")).toBe("review")
    expect(phaseForStep("acceptance")).toBe("agree")
    expect(phaseScale("details")).toBe(0.25)
    expect(phaseScale("agree")).toBe(1)
  })

  it("mede a senha com texto, não só com a barra", () => {
    expect(passwordStrength("").level).toBe("empty")
    expect(passwordStrength("curta").level).toBe("short")
    expect(passwordStrength("senha-segura").level).toBe("good")
    expect(passwordStrength("Senha-segura-1").level).toBe("strong")
    expect(pt.registration.strength.strong).toBe("Forte")
  })

  it("deixa a senha vazia ao reaproveitar os campos do chat", () => {
    const values = formValuesFromFields({
      full_name: "Ana Costa",
      email: "ana@example.com",
      phone: null,
      visitor_type: null,
      visit_reason: null,
    })
    expect(values.full_name).toBe("Ana Costa")
    expect(values.email).toBe("ana@example.com")
    expect(values.password).toBe("")
    expect(values.accept_terms).toBe(false)
    expect(values.profile_personalization).toBe(false)
  })

  it("exige os aceites obrigatórios e começa com os opcionais desmarcados", () => {
    const empty = emptyConsents()
    expect(empty.profile_personalization).toBe(false)
    expect(empty.quality_improvement).toBe(false)
    expect(consentIssues(empty)).toEqual({
      accept_terms: pt.registration.termsRequired,
      age_18_plus: pt.registration.ageRequired,
    })
    expect(
      consentIssues({ ...empty, accept_terms: true, age_18_plus: true })
    ).toEqual({})
  })

  it("reconhece o e-mail que já tem conta", () => {
    expect(
      emailOffersSignIn("Este e-mail já tem uma conta. Entre para continuar.")
    ).toBe(true)
    expect(emailOffersSignIn(pt.registration.emailInvalid)).toBe(false)
  })

  it("não coloca a senha nos campos do resumo", () => {
    const parsed = registrationFormSchema.safeParse({
      ...formValuesFromFields(null),
      full_name: "Ana Costa",
      email: "ana@example.com",
      password: "senha-segura-1",
      accept_terms: true,
      age_18_plus: true,
    })
    expect(parsed.success).toBe(true)
    if (!parsed.success) {
      return
    }
    const payload = toFormPayload(parsed.data, "2026-10-25.1", null)
    expect(payload.password).toBe("senha-segura-1")
    expect(payload).not.toHaveProperty("fields")
    expect(payload.profile_personalization).toBe(false)
  })
})
