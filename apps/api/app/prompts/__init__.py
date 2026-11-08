"""Textos visíveis ao usuário, em português.

Camada de prompts (seção 6.2 do SDD e `.claude/rules/camadas.md`): as respostas fixas, as
mensagens de erro, as falas do cadastro e os prompts enviados ao modelo moram aqui, em
português; código, rotas e identificadores ficam em inglês. Serviços, workflows, adaptadores,
controladores e scripts importam estas constantes.

Os prompts do modelo têm versão. `qa.py`, `registration.py` e `evals.py` declaram uma
`*_PROMPT_VERSION` por prompt, e `tests/unit/test_prompt_versions.py` trava o hash SHA-256 do
texto de cada versão: mudar uma letra de um prompt exige uma versão nova (seção 10.2 e
ADR-007). A versão vai para cada mensagem gravada e para cada rastro.
"""
