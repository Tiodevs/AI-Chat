# attendance

O console da equipe de atendimento humano e a lista de encerrados do admin: as telas `/attendance`, `/attendance/commitment` e `/admin/attendance`, os hooks que falam com a API e o fluxo SSE do console. É uma feature do frontend, com view, controlador e estado da [seção 13.2 do SDD](../../../../../docs/sdd/experiencia.md#132-mvc-no-frontend), sobre a [seção 29](../../../../../docs/sdd/atendimento-humano.md).

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [`model.ts`](model.ts) | Tipos e conversões das respostas da API para as views, a junção de mensagens pelo id, o título da aba só com a contagem e a duração em minutos. | Os hooks e as telas desta pasta |
| [`useAttendance.ts`](useAttendance.ts) | Controlador e store do console: presença, aceite, fila, abas, assumir, responder, orientação de emergência, remover, devolver, encerrar e o fluxo `GET /v1/attendance/events`. | [`app/routes/attendance.tsx`](../../app/routes/attendance.tsx), [`app/routes/attendance-commitment.tsx`](../../app/routes/attendance-commitment.tsx), `useSignOut` e `src/test/setup.ts` |
| [`useClosedHandoffs.ts`](useClosedHandoffs.ts) | A lista de encerrados pelo TanStack Query e a leitura de um encerrado com motivo. | [`app/routes/admin-attendance.tsx`](../../app/routes/admin-attendance.tsx) |
| [`attendance-screen.tsx`](attendance-screen.tsx) | Tela `/attendance`: presença, os três `StatTile`, a `QueueList` e até 3 atendimentos em `Tabs`, com o `HandoffThread`, o compositor e as ações. | `app/routes/attendance.tsx` |
| [`commitment-screen.tsx`](commitment-screen.tsx) | Tela `/attendance/commitment`: os dez itens do compromisso, a caixa de aceite e Aceitar e continuar. | `app/routes/attendance-commitment.tsx` |
| [`closed-screen.tsx`](closed-screen.tsx) | Tela `/admin/attendance`: a `DataTable` dos encerrados, o motivo num `Dialog` e a conversa num `Sheet` só de leitura. | `app/routes/admin-attendance.tsx` |
| [`attendance.test.tsx`](attendance.test.tsx) | Testes do título da aba, da fila sem conteúdo, do evento `queue` e da navegação de cada papel. | Vitest |

## Como ler

1. `model.ts`, para os tipos.
2. `useAttendance.ts`: `loadConsole`, as ações e `applyEvent`, lido ao lado da tabela de eventos do console da seção 29.6.
3. As telas e, em `components/patterns`, o `PresenceToggle`, a `QueueList`, o `HandoffThread` e o `RedactDialog`.

## Testes

`attendance.test.tsx` roda no projeto `dom` do Vitest, sem a API. Os fluxos do servidor estão em `apps/api/tests/integration/test_handoff.py` e `test_realtime.py`.

## Leia também

- SDD [29. Atendimento humano](../../../../../docs/sdd/atendimento-humano.md), com as rotas na seção 29.10 e as telas na 29.11.
- A conversa do visitante, em [`features/ask`](../ask/README.md).
