"""Citação válida e telefone presente no contexto. Seção 7.1 do SDD.

Camada de domínio. Fundamentar é conferir, com código e sem outro modelo, que a resposta só
cita blocos que existem e só traz telefone que está no texto recuperado. `QaWorkflow`
(`app/workflows/qa.py`) chama `check_grounding` com o rascunho completo, depois do fluxo
(passo 7 da seção 7.1). `Citation` também é gravada em `messages.citations` e lida pelo
repositório de conversas, pela exportação da conta e pelo script `ask`.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

# O mesmo formato mascarado nos logs, mais o grupo 3-3-4 com espaço ou ponto.
# Casa `(555) 014-2600`, um número internacional com `+` e o grupo 3-3-4. Um número só com sete
# dígitos, como `014-2600`, não casa e passa sem conferência. `trace_policy._PHONE_RE` repete
# esta expressão.
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\(\d{3}\)\s*\d{3}-\d{4}|\+\d[\d\s().-]{7,}\d|\d{3}[-.\s]\d{3}[-.\s]\d{4})(?!\w)"
)
# Aceita [2] e também o grupo [2, 3] ou [2; 3], que o modelo às vezes escreve.
_CITATION_RE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
# Separa os índices de um grupo pela vírgula ou pelo ponto e vírgula.
_CITATION_SPLIT_RE = re.compile(r"\s*[,;]\s*")


@dataclass(frozen=True, slots=True)
class ContextBlock:
    """Um bloco de contexto numerado, como o gerador o vê.

    `index` começa em 1, na ordem da busca híbrida, e é o número que o modelo cita como `[1]`.
    O workflow monta um bloco por chunk acima do piso de similaridade, até 6.
    """

    index: int
    chunk_id: UUID
    document_title: str
    heading: str | None
    content: str


@dataclass(frozen=True, slots=True)
class Citation:
    """Citação mantida na resposta.

    Vira um evento `citation` do SSE (seção 7.1), um chip na interface, e fica gravada em
    `messages.citations`.
    """

    index: int
    document_title: str
    heading: str | None
    chunk_id: UUID


@dataclass(frozen=True, slots=True)
class GroundingDecision:
    """Resultado da conferência.

    Com `grounded` falso, o workflow grava `grounding_failed` e troca o rascunho pelo texto
    fixo de abstenção; a interface recebe o evento `replace` (seção 7.1).
    """

    grounded: bool
    citations: tuple[Citation, ...]


def check_grounding(draft: str, blocks: Sequence[ContextBlock]) -> GroundingDecision:
    """Uma citação fica só quando o índice existe. Um telefone ausente reprova.

    1. Um telefone do rascunho que não aparece no contexto reprova, mesmo com citação válida.
    2. Só ficam as citações cujo índice existe nos blocos, uma vez cada, na ordem do texto.
    3. Sem nenhuma citação válida, o rascunho reprova.

    O texto do rascunho não muda: um marcador sem bloco, como `[9]`, continua no texto de uma
    resposta aprovada e só não vira citação.
    """
    # 1.
    if _phone_outside_context(draft, blocks):
        return GroundingDecision(grounded=False, citations=())
    # 2.
    citations = _citations(draft, blocks)
    # 3.
    if not citations:
        return GroundingDecision(grounded=False, citations=())
    return GroundingDecision(grounded=True, citations=tuple(citations))


def _phone_outside_context(draft: str, blocks: Sequence[ContextBlock]) -> bool:
    """Verdadeiro se algum telefone do rascunho não aparece no contexto.

    A comparação usa só os dígitos, então `(555) 014-2600` casa com `555.014.2600`. Os dígitos
    do contexto inteiro são concatenados, então um telefone também passa quando os dígitos
    dele aparecem em sequência, mesmo vindos de números vizinhos.
    """
    context = _digits(_context_text(blocks))
    return any(_digits(match.group(0)) not in context for match in _PHONE_RE.finditer(draft))


def _citations(draft: str, blocks: Sequence[ContextBlock]) -> list[Citation]:
    """Citações válidas, sem repetir índice, na ordem em que aparecem no rascunho."""
    by_index = {block.index: block for block in blocks}
    found: list[Citation] = []
    seen: set[int] = set()
    for match in _CITATION_RE.finditer(draft):
        for raw in _CITATION_SPLIT_RE.split(match.group(1)):
            index = int(raw)
            block = by_index.get(index)
            if block is None or index in seen:
                continue
            seen.add(index)
            found.append(
                Citation(
                    index=index,
                    document_title=block.document_title,
                    heading=block.heading,
                    chunk_id=block.chunk_id,
                )
            )
    return found


def _context_text(blocks: Sequence[ContextBlock]) -> str:
    """Título de seção e conteúdo de cada bloco: o telefone pode estar em qualquer um dos dois."""
    parts: list[str] = []
    for block in blocks:
        if block.heading:
            parts.append(block.heading)
        parts.append(block.content)
    return "\n".join(parts)


def _digits(value: str) -> str:
    """Só os dígitos do texto, na ordem."""
    return "".join(character for character in value if character.isdigit())
