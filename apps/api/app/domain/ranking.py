"""Fusão de rankings. Os ranks começam em 1. Seção 8.4 do SDD.

Camada de domínio. `RetrievalService.search_by_vector` (`app/services/retrieval.py`) funde a
lista da busca por vetor com a da busca por palavra-chave e corta em `RESULT_LIMIT`;
`QaWorkflow` usa `RESULT_LIMIT` de novo ao montar os blocos de contexto.

Reciprocal rank fusion (RRF) dá a cada item a soma de `1 / (k + posição)` nas listas em que ele
aparece. A fusão usa só a posição, não a nota de cada busca, então junta listas com escalas
diferentes, como a similaridade de cosseno e a relevância do texto completo. Um item bem
colocado nas duas listas sobe.
"""

from collections.abc import Sequence

# Constante da fusão (seção 8.4). Com `k` grande, a 1ª e a 2ª posição valem quase o mesmo:
# 1/61 e 1/62.
RRF_K = 60
# Até 20 candidatos de cada busca e 6 blocos para o gerador (seção 8.4).
VECTOR_CANDIDATES = 20
KEYWORD_CANDIDATES = 20
RESULT_LIMIT = 6


def reciprocal_rank_fusion[T](rankings: Sequence[Sequence[T]], *, k: int = RRF_K) -> list[T]:
    """Funde várias listas ordenadas numa só, por reciprocal rank fusion.

    1. Em cada lista, a posição começa em 1. Um item repetido na mesma lista conta só na
       primeira vez, e a repetição não ocupa posição.
    2. A nota do item é a soma de `1 / (k + posição)` nas listas em que ele aparece.
    3. A ordem final é a nota, da maior para a menor. No empate, vem primeiro o item visto
       antes, lendo as listas na ordem recebida, então o resultado é sempre o mesmo.

    Devolve todos os itens; quem chama corta em `RESULT_LIMIT`. `[T]` declara um tipo genérico
    (PEP 695): na busca, os itens são ids de chunk, mas qualquer valor que sirva de chave de
    `dict` funciona.
    """
    scores: dict[T, float] = {}
    first_seen: dict[T, int] = {}
    seen_count = 0
    for ranking in rankings:
        seen_in_list: set[T] = set()
        rank = 0
        for item in ranking:
            # 1.
            if item in seen_in_list:
                continue
            seen_in_list.add(item)
            rank += 1
            if item not in first_seen:
                first_seen[item] = seen_count
                seen_count += 1
            # 2.
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    # 3.
    return sorted(scores, key=lambda item: (-scores[item], first_seen[item]))
