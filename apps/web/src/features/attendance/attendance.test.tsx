/**
 * O console de atendimento: título da aba sem conteúdo, fila sem conteúdo,
 * eventos do fluxo e a navegação de cada papel. Seções 29.3, 29.9.4 e 29.11.
 *
 * Renderiza a `QueueList` e chama `applyEvent` e `navigationFor` direto, sem
 * a API. Projeto `dom` do Vitest. Não usa a API nem banco.
 */
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { navigationFor } from "@/app/navigation.ts"
import { AppProviders } from "@/app/providers.tsx"
import { QueueList } from "@/components/patterns/queue-list.tsx"
import { pt } from "@/i18n/pt.ts"

import { consoleTitle } from "./model.ts"
import {
  applyEvent,
  resetAttendanceState,
  selectConsole,
} from "./useAttendance.ts"

afterEach(() => {
  resetAttendanceState()
})

describe("console de atendimento", () => {
  it("o título da aba só leva a contagem de novidades", () => {
    // Etapa 17.7, CA-1 (seção 29.9.4).
    expect(consoleTitle(2)).toBe("(2) Atendimento · Atrium")
    expect(consoleTitle(0)).toBe(`${pt.pages.attendance} · ${pt.appName}`)
  })

  it("a fila mostra o rótulo, a espera e o motivo, sem conteúdo", async () => {
    // Etapa 17.7, CA-1 (FR-22, seção 29.9.4).
    const onTake = vi.fn()
    render(
      <AppProviders>
        <QueueList
          items={[
            {
              handoffId: "h1",
              label: "Visitante 3f9a1c22",
              queuedAt: "2026-11-12T15:00:00Z",
              trigger: "abstained",
              returned: true,
              visitorPresent: false,
            },
          ]}
          now={new Date("2026-11-12T15:03:00Z")}
          canTake
          onTake={onTake}
        />
      </AppProviders>
    )
    expect(screen.getByText("Visitante 3f9a1c22")).toBeTruthy()
    expect(screen.getByText("Esperando há 3 minutos")).toBeTruthy()
    expect(screen.getByText(pt.attendance.triggers.abstained)).toBeTruthy()
    expect(screen.getByText(pt.attendance.returned)).toBeTruthy()
    expect(screen.getByText(pt.attendance.visitorAway)).toBeTruthy()
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: /Assumir/ }))
    expect(onTake).toHaveBeenCalledWith("h1")
  })

  it("o evento queue não leva campo de conteúdo para a tela", () => {
    applyEvent({
      event: "queue",
      data: JSON.stringify({
        queued: [
          {
            handoff_id: "h1",
            label: "Visitante 3f9a1c22",
            requested_at: "2026-11-12T15:00:00Z",
            queued_at: "2026-11-12T15:00:00Z",
            trigger: "abstained",
            returned: false,
            visitor_present: true,
          },
        ],
        available_attendants: 2,
      }),
    })
    const state = selectConsole()
    expect(state.availableAttendants).toBe(2)
    expect(state.queue).toHaveLength(1)
    expect(Object.keys(state.queue[0] ?? {}).sort()).toEqual([
      "handoffId",
      "label",
      "queuedAt",
      "returned",
      "trigger",
      "visitorPresent",
    ])
  })
})

describe("navegação do atendimento", () => {
  it("o attendant vê só Atendimento e Conta, sem os encerrados", () => {
    const groups = navigationFor("attendant")
    expect(new Set(groups.map((group) => group.label))).toEqual(
      new Set([pt.nav.account, pt.nav.attendanceGroup])
    )
    const attendance = groups.find(
      (group) => group.label === pt.nav.attendanceGroup
    )
    expect(attendance?.items.map((item) => item.to)).toEqual(["/attendance"])
  })

  it("o admin vê a fila e os encerrados, e o membro não vê o grupo", () => {
    const admin = navigationFor("admin").find(
      (group) => group.label === pt.nav.attendanceGroup
    )
    expect(admin?.items.map((item) => item.to)).toEqual([
      "/attendance",
      "/admin/attendance",
    ])
    expect(
      navigationFor("member").some(
        (group) => group.label === pt.nav.attendanceGroup
      )
    ).toBe(false)
  })
})
