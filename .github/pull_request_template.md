## O que muda

<!-- Resumo da mudança e o motivo. -->

## Seção do SDD

<!-- Ex.: SDD 7.2. Se o comportamento mudou, o SDD foi atualizado nesta PR? -->

## Como testei

- [ ] API: `uv run ruff check && uv run mypy && uv run pytest`
- [ ] Web: `pnpm exec eslint . && pnpm test`
- [ ] Typecheck, build e Storybook
- [ ] Playwright, quando a interface mudou

## Capturas de tela

<!-- Quando a interface mudar. -->

## Checklist

- [ ] Texto visível ao usuário em português; código em inglês
- [ ] Nenhum `.env`, chave ou senha no diff
- [ ] Testes não chamam Gemini nem LangSmith
- [ ] `PROMPT_VERSION` atualizada se um prompt mudou
