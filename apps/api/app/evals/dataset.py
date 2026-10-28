"""Diferença entre o arquivo e o dataset do LangSmith. Sem rede."""

import json
from dataclasses import dataclass

from app.evals.cases import EvalCase, example_inputs, example_outputs


@dataclass(frozen=True, slots=True)
class RemoteExample:
    example_id: str
    case_id: str | None
    inputs: dict[str, object]
    outputs: dict[str, object]


@dataclass(frozen=True, slots=True)
class SyncPlan:
    create: tuple[EvalCase, ...]
    update: tuple[tuple[str, EvalCase], ...]
    delete: tuple[str, ...]


def plan_sync(local: tuple[EvalCase, ...], remote: tuple[RemoteExample, ...]) -> SyncPlan:
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
    for case_id, matches in by_case.items():
        if case_id not in seen:
            delete.extend(example.example_id for example in matches)
    return SyncPlan(create=tuple(create), update=tuple(update), delete=tuple(delete))


def _canonical(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
