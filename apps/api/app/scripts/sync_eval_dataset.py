"""Sincroniza evals/public_qa.jsonl com o dataset atrium-public-qa. Seção 21.2.

Uso: `python -m app.scripts.sync_eval_dataset`, em `apps/api`, depois de mudar o arquivo de
casos e antes do `run_evals`.

Cria o dataset se ele não existe, lista os exemplos e aplica o plano de `app.evals.dataset`:
cria os casos novos, atualiza os que mudaram e apaga os que saíram do arquivo. Cada exemplo
guarda o `case_id` nos metadados, que é o que liga o exemplo ao caso. Não usa banco nem o
Gemini. Precisa de `LANGSMITH_API_KEY`, mais `LANGSMITH_WORKSPACE_ID` com chave de
organização. O `evals.yml` roda este script antes de cada experimento.
"""

import sys

from langsmith import Client

from app.adapters.langsmith_tracing import langsmith_api_url
from app.core.config import Settings
from app.evals.cases import DATASET_NAME, EvalCase, example_inputs, example_outputs, load_cases
from app.evals.dataset import RemoteExample, plan_sync


def main() -> None:
    """Confere a chave, sincroniza e imprime quantos exemplos foram criados, mudados e apagados."""
    settings = Settings()
    if not settings.langsmith_api_key:
        print("Defina LANGSMITH_API_KEY.", file=sys.stderr)
        raise SystemExit(1)
    cases = load_cases()
    client = Client(
        api_key=settings.langsmith_api_key,
        api_url=langsmith_api_url(settings.langsmith_endpoint),
        workspace_id=settings.langsmith_workspace_id or None,
        hide_inputs=False,
        hide_outputs=False,
    )
    try:
        created, updated, deleted = _sync(client, cases)
    finally:
        client.flush()
        client.close()
    print(f"Dataset {DATASET_NAME}: {created} novos, {updated} atualizados, {deleted} removidos.")


def _sync(client: Client, cases: tuple[EvalCase, ...]) -> tuple[int, int, int]:
    """Aplica o plano no LangSmith e devolve as contagens de criados, mudados e apagados.

    No SDK, `create_example` recebe o esperado em `reference_outputs`, e `update_example`, em
    `outputs`.
    """
    if not client.has_dataset(dataset_name=DATASET_NAME):
        client.create_dataset(
            DATASET_NAME,
            description="Perguntas públicas do Atrium. Fonte: evals/public_qa.jsonl.",
        )
    remote = tuple(_remote(example) for example in client.list_examples(dataset_name=DATASET_NAME))
    plan = plan_sync(cases, remote)
    for case in plan.create:
        client.create_example(
            inputs=example_inputs(case),
            reference_outputs=example_outputs(case),
            metadata={"case_id": case.id},
            dataset_name=DATASET_NAME,
        )
    for example_id, case in plan.update:
        client.update_example(
            example_id,
            inputs=example_inputs(case),
            outputs=example_outputs(case),
            metadata={"case_id": case.id},
        )
    if plan.delete:
        client.delete_examples(list(plan.delete))
    return len(plan.create), len(plan.update), len(plan.delete)


def _remote(example: object) -> RemoteExample:
    """Um exemplo do SDK como `RemoteExample`, lido com `getattr` para tolerar campos ausentes."""
    metadata = getattr(example, "metadata", None)
    case_id = metadata.get("case_id") if isinstance(metadata, dict) else None
    inputs = getattr(example, "inputs", None) or {}
    outputs = getattr(example, "outputs", None) or {}
    return RemoteExample(
        example_id=str(getattr(example, "id", "")),
        case_id=case_id if isinstance(case_id, str) else None,
        inputs=dict(inputs),
        outputs=dict(outputs),
    )


if __name__ == "__main__":
    main()
