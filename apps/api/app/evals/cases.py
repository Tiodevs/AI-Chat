"""Casos de evals/public_qa.jsonl. Seção 21.2 do SDD.

Lê e valida o arquivo de casos, uma linha JSON por caso, e converte cada caso nas entradas e
nas saídas de referência de um exemplo do dataset do LangSmith. Não usa rede. Quem usa: os
scripts `sync_eval_dataset` e `run_evals`, `dataset.py`, `summary.py` e
`tests/unit/test_evaluators.py`.
"""

import json
from dataclasses import dataclass
from pathlib import Path

# O nome do dataset no LangSmith (seção 21.2).
DATASET_NAME = "atrium-public-qa"
# Seções 5.3 e 21.2: pelo menos 90% dos casos que esperam resposta com `outcome_match`.
ANSWER_MATCH_THRESHOLD = 0.9


@dataclass(frozen=True, slots=True)
class EvalCase:
    """Um caso do conjunto público.

    `expected_outcome` lista os desfechos aceitos: um só, ou alternativas como no caso
    `follow-up`. `expected_document_slug` é o documento que precisa estar entre as citações,
    ou `None` quando o caso não exige fonte. `prior_question` é a pergunta anterior de um caso
    de continuação, e `forbidden_text`, um trecho que a resposta não pode conter.
    """

    id: str
    question: str
    expected_outcome: tuple[str, ...]
    expected_document_slug: str | None
    prior_question: str | None = None
    forbidden_text: str | None = None

    @property
    def expects_answer(self) -> bool:
        """Diz se o caso entra na taxa do limiar: só quando `answered` é o único aceito.

        Um caso com alternativas, como `follow-up` e `ignore-docs`, fica fora da taxa.
        """
        return self.expected_outcome == ("answered",)


def repo_root() -> Path:
    """A raiz do repositório: quatro pastas acima de `apps/api/app/evals`."""
    return Path(__file__).resolve().parents[4]


def cases_path() -> Path:
    """O arquivo de casos, `evals/public_qa.jsonl`, revisado por pull request."""
    return repo_root() / "evals" / "public_qa.jsonl"


def catalog_path() -> Path:
    """O catálogo do corpus (seção 9), de onde saem os telefones conhecidos."""
    return repo_root() / "docs" / "sdd" / "corpus.md"


def load_cases(path: Path | None = None) -> tuple[EvalCase, ...]:
    """Os casos do arquivo, na ordem das linhas. Linhas em branco são puladas.

    Levanta `ValueError`, com o número da linha, para uma linha que não é objeto, um caso
    sem `id`, sem `question` ou sem `expected_outcome`, um `id` repetido ou um arquivo vazio.
    Um JSON inválido levanta o erro do módulo `json`.
    """
    source = cases_path() if path is None else path
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"line {line_number} is not an object")
        case = _case(payload, line_number)
        if case.id in seen:
            raise ValueError(f"duplicate case {case.id}")
        seen.add(case.id)
        cases.append(case)
    if not cases:
        raise ValueError("eval file is empty")
    return tuple(cases)


def example_inputs(case: EvalCase) -> dict[str, object]:
    """As entradas do exemplo no LangSmith, que o alvo do `run_evals` recebe.

    O `id` vai junto para o alvo nomear o `request_id` e para o resumo achar o caso de cada
    saída.
    """
    payload: dict[str, object] = {"id": case.id, "question": case.question}
    if case.prior_question:
        payload["prior_question"] = case.prior_question
    return payload


def example_outputs(case: EvalCase) -> dict[str, object]:
    """As saídas de referência do exemplo, que os avaliadores recebem.

    `expected_outcome` vira texto quando há um desfecho só e lista quando há alternativas.
    O documento e o trecho proibido só entram quando o caso os define.
    """
    outcome: object = (
        case.expected_outcome[0] if len(case.expected_outcome) == 1 else list(case.expected_outcome)
    )
    payload: dict[str, object] = {"expected_outcome": outcome}
    if case.expected_document_slug:
        payload["expected_document_slug"] = case.expected_document_slug
    if case.forbidden_text:
        payload["forbidden_text"] = case.forbidden_text
    return payload


def _case(payload: dict[str, object], line_number: int) -> EvalCase:
    """Um `EvalCase` a partir de uma linha. Texto vazio em campo opcional vira `None`."""
    identifier = payload.get("id")
    question = payload.get("question")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError(f"line {line_number} needs an id")
    if not isinstance(question, str) or not question.strip():
        raise ValueError(f"line {line_number} needs a question")
    prior = payload.get("prior_question")
    forbidden = payload.get("forbidden_text")
    slug = payload.get("expected_document_slug")
    return EvalCase(
        id=identifier,
        question=question,
        expected_outcome=_outcomes(payload.get("expected_outcome"), line_number),
        expected_document_slug=slug if isinstance(slug, str) and slug else None,
        prior_question=prior if isinstance(prior, str) and prior else None,
        forbidden_text=forbidden if isinstance(forbidden, str) and forbidden else None,
    )


def _outcomes(value: object, line_number: int) -> tuple[str, ...]:
    """O desfecho esperado, em texto ou em lista não vazia de textos, como tupla."""
    if isinstance(value, str) and value:
        return (value,)
    if isinstance(value, list) and value and all(isinstance(item, str) and item for item in value):
        return tuple(value)
    raise ValueError(f"line {line_number} needs expected_outcome")
