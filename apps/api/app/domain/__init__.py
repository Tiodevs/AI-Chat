"""Regras puras do Atrium: a camada de domínio. Sem I/O e sem framework.

Cada módulo guarda as decisões de um assunto: a máquina de estados do cadastro, as regras de
campo, a fundamentação da resposta, a fusão de rankings, os desfechos, os limites de taxa, a
retenção e os erros de domínio. Serviços, workflows, repositórios e adaptadores chamam estas
funções. O domínio não chama nenhum deles.

O domínio importa só a biblioteca padrão e o Pydantic (seção 6.2 do SDD e
`.claude/rules/camadas.md`). O teste de `tests/architecture` falha se um módulo daqui importar
outra coisa. Por isso nenhuma regra lê o relógio, o banco ou a rede: quem chama passa o `now`
e os dados já carregados, e recebe de volta um valor ou o motivo da recusa.
"""
