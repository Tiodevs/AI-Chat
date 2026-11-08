"""Diferença entre o arquivo e o dataset do LangSmith. Sem rede.

O arquivo `evals/public_qa.jsonl` é a fonte (seção 21.2). Este módulo compara os casos dele com
os exemplos que já estão no dataset e diz o que criar, atualizar e apagar. Um exemplo remoto se
liga a um caso pelo `case_id` dos metadados. Quem usa: o script `sync_eval_dataset`, que aplica
o plano, e `tests/unit/test_evaluators.py`.
"""

import json
from dataclasses import dataclass

from app.evals.cases import EvalCase, example_inputs, example_outputs


@dataclass(frozen=True, slots=True)
class RemoteExample:
    """Um exemplo do dataset no LangSmith. `case_id` é `None` quando falta nos metadados."""

    example_id: str
    case_id: str | None
    inputs: dict[str, object]
    outputs: dict[str, object]


@dataclass(frozen=True, slots=True)
class SyncPlan:
    """O que a sincronização faz no dataset.

    `create` tem os casos a criar; `update`, os pares `(id do exemplo, caso)` a atualizar; e
    `delete`, os ids dos exemplos a apagar.
    """

    create: tuple[EvalCase, ...]
    update: tuple[tuple[str, EvalCase], ...]
    delete: tuple[str, ...]


def plan_sync(local: tuple[EvalCase, ...], remote: tuple[RemoteExample, ...]) -> SyncPlan:
    """O plano que deixa o dataset igual ao arquivo.

    1. Agrupa os exemplos remotos por `case_id`. Um exemplo sem `case_id` é apagado.
    2. Para cada caso do arquivo: sem exemplo, cria. Com vários, mantém o primeiro e apaga os
       outros. Se o mantido difere nas entradas ou nas saídas de referência, atualiza.
    3. Apaga os exemplos de casos que saíram do arquivo.
    """
    # 1.
    by_case: dict[str, list[RemoteExample]] = {}
    orphans: list[str] = []
    for example in remote:
        if example.case_id is None:
            orphans.append(example.example_id)
            continue
        by_case.setdefault(example.case_id, []).append(example)
    create: list[EvalCase] = []
    update: list[tuple[str, EvalCase]] = []
    delete = list(orphans)
    seen: set[str] = set()
    # 2.
    for case in local:
        seen.add(case.id)
        matches = by_case.get(case.id, [])
        if not matches:
            create.append(case)
            continue
        keeper = matches[0]
        delete.extend(example.example_id for example in matches[1:])
        if _canonical(keeper.inputs) != _canonical(example_inputs(case)) or _canonical(
            keeper.outputs
        ) != _canonical(example_outputs(case)):
            update.append((keeper.example_id, case))
    # 3.
    for case_id, matches in by_case.items():
        if case_id not in seen:
            delete.extend(example.example_id for example in matches)
    return SyncPlan(create=tuple(create), update=tuple(update), delete=tuple(delete))


def _canonical(payload: dict[str, object]) -> str:
    """JSON com as chaves ordenadas, para a ordem das chaves não parecer uma mudança."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
