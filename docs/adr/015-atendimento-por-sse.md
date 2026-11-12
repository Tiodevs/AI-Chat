# ADR-015 — Atendimento humano em tempo real por SSE e `POST`, sem WebSocket

Proposto em 2026-11-10 e aceito em 2026-11-12, na Etapa 17.0 (seção 29 do SDD, decisão D-5).

## Contexto

O atendimento humano da seção 29 precisa empurrar mensagens e mudanças de status para o visitante e para a equipe enquanto a conversa acontece. O navegador fala só com a origem do frontend: a Vercel encaminha `/backend/*` para a API (ADR-001). É isso que mantém o cookie de sessão primário, o segredo da borda que a API exige em `/v1` (seção 10.3), o IP confiável dos limites de taxa (seção 10.4) e a CSP com `connect-src 'self'` (seção 13.4).

O que as plataformas documentam em 2026-11-10:

- A Vercel serve WebSocket só nas Vercel Functions, em beta desde 2026-06-22. A documentação dos rewrites para origens externas não fala do upgrade para WebSocket ([WebSocket nas Vercel Functions](https://vercel.com/support/articles/do-vercel-serverless-functions-support-websocket-connections), [rewrites](https://vercel.com/docs/routing/rewrites)).
- A Vercel espera até 120 segundos pelo primeiro byte da origem e mantém o pedido aberto enquanto chegam dados pelo menos a cada 120 segundos ([changelog de 2025-05-08](https://vercel.com/changelog/cdn-origin-timeout-increased-to-two-minutes)).
- A Railway mantém um pedido HTTP por até 15 minutos enquanto passam dados e o fecha depois de 5 minutos sem dados. Uma conexão WebSocket fica fora desses limites ([limites da Railway](https://docs.railway.com/networking/public-networking/specs-and-limits)).

O SSE das perguntas já passa pelo rewrite, com manutenção a cada 15 segundos, e a fumaça confere o fluxo em cada deploy (seção 22.3).

## Decisão

O servidor fala com o navegador por SSE (`GET`), e o navegador fala com o servidor por `POST`, tudo em `/backend/v1`, pelo mesmo rewrite. Cada fluxo dura até 10 minutos e termina com o evento `reconnect`. O navegador reconecta com `Last-Event-ID`, e o servidor reenvia o que tem `seq` maior (seção 29.6).

## Consequências

- Cookie, conferência de `Origin`, segredo da borda, IP dos limites e CSP continuam como estão. Nenhum operador novo recebe o conteúdo do atendimento.
- O canal é de mão única. Cada mensagem enviada é um `POST`, com a latência de um pedido mais um aviso do banco (ADR-016).
- O navegador reconecta a cada 10 minutos e depois de cada queda. A retomada pelo `seq` é obrigatória, testada e medida.
- O fluxo depende do comportamento do rewrite com conexões longas, que a Vercel documenta só como tempo entre bytes. A Etapa 17.3 mede um fluxo de 12 minutos em development.
- Um domínio próprio, com a API num subdomínio do mesmo site, deixaria abrir WebSocket sem perder o cookie de mesma origem. Esse é o caminho se o atendimento precisar de canal bidirecional (seção 25).

## Alternativas

- **WebSocket pelo rewrite da Vercel.** Não está documentado para origens externas. Se funcionar hoje, pode parar sem aviso, e a fumaça não teria como garantir.
- **WebSocket direto na Railway.** O cookie `SameSite=Lax` da origem da Vercel não vai para outro site, então seria preciso um bilhete de curta duração. A conexão pularia o segredo da borda e o IP confiável, exigiria conferir `Origin` no upgrade contra o sequestro de WebSocket entre sites, mudaria a CSP e exporia a URL da Railway no frontend.
- **Serviço de tempo real de terceiros, como Ably ou Pusher.** Um operador novo com o conteúdo do atendimento, outra transferência internacional, outro custo e outra chave no navegador.
- **Só consulta periódica.** Latência de segundos e um pedido por segundo por tela aberta. Fica como reserva da visão, como na seção 7.1.
