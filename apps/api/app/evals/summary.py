"""Resumo do outcome_match nos casos que esperam resposta. Seção 5.3.

O resumo em Markdown que o `run_evals` imprime e grava em `EVAL_SUMMARY_PATH`; o `evals.yml`
o publica no resumo do job e o comenta na pull request (seção 21.2). A taxa conta só os casos
em que `answered` é o único desfecho aceito, contra o limiar de 90%. O resumo traz só o
`outcome_match`; a Etapa 16.1 acrescenta `source_match` e `groundedness`. Quem usa: o script
`run_evals` e `tests/unit/test_evaluators.py`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.evals.cases import ANSWER_MATCH_THRESHOLD, EvalCase
from app.evals.evaluators import outcome_matches


@dataclass(frozen=True, slots=True)
class AnswerMatch:
    """A taxa de `outcome_match` nos casos que esperam resposta, com os ids que falharam."""

    rate: float
    matched: int
    total: int
    failed_ids: tuple[str, ...]

    @property
    def meets_threshold(self) -> bool:
        """Diz se a taxa alcança os 90%.

        A folga de 1e-9 evita que um arredondamento de ponto flutuante reprove uma taxa igual
        ao limiar.
        """
        return self.rate + 1e-9 >= ANSWER_MATCH_THRESHOLD


def answer_match(
    cases: Sequence[EvalCase],
    actual_outcomes: Mapping[str, str],
    texts: Mapping[str, str],
) -> AnswerMatch:
    """A taxa de `outcome_match` nos casos com `expects_answer`.

    Um caso sem saída conta como falha. Sem nenhum caso relevante, a taxa é 1.
    """
    relevant = [case for case in cases if case.expects_answer]
    failed: list[str] = []
    matched = 0
    for case in relevant:
        actual = actual_outcomes.get(case.id, "")
        if outcome_matches(
            case.expected_outcome,
            actual,
            texts.get(case.id, ""),
            case.forbidden_text,
        ):
            matched += 1
        else:
            failed.append(case.id)
    total = len(relevant)
    rate = 1.0 if total == 0 else matched / total
    return AnswerMatch(rate=rate, matched=matched, total=total, failed_ids=tuple(failed))


def render_summary(
    *,
    prompt_version: str,
    match: AnswerMatch,
    rows: Sequence[tuple[str, str, str, int]],
    experiment_name: str | None,
    experiment_url: str | None,
    baseline: str | None,
) -> str:
    """O Markdown do resumo: taxa, limiar, experimento, linha de base e uma linha por caso.

    `rows` traz `(id, esperado, obtido, outcome_match)` de todos os casos, não só dos que
    entram na taxa. Abaixo do limiar, o texto lembra que o merge não é bloqueado, mas pede
    justificativa escrita na pull request (seção 21.2).
    """
    lines = [
        "## Avaliação atrium-public-qa",
        "",
        f"Versão do prompt: `{prompt_version}`",
        (
            "outcome_match nos casos que esperam resposta: "
            f"{match.rate:.0%} ({match.matched}/{match.total})"
        ),
        f"Limiar: {ANSWER_MATCH_THRESHOLD:.0%}",
    ]
    if experiment_name:
        lines.append(f"Experimento: `{experiment_name}`")
    if experiment_url:
        lines.append(f"Comparação: {experiment_url}")
    if baseline:
        lines.append(f"Linha de base de main: {baseline}")
    else:
        lines.append("Linha de base de main: ainda não há experimento com `git_ref=main`.")
    if match.meets_threshold:
        lines.append("O limiar foi atingido.")
    else:
        lines.extend(
            [
                "O limiar não foi atingido. Isso não bloqueia o merge.",
                "Uma queda abaixo de 90% pede justificativa escrita na pull request.",
                "Casos que falharam: " + ", ".join(f"`{item}`" for item in match.failed_ids),
            ]
        )
    lines.extend(["", "| Caso | Esperado | Obtido | outcome_match |", "|---|---|---|---|"])
    for case_id, expected, actual, score in rows:
        lines.append(f"| `{case_id}` | {expected} | {actual} | {score} |")
    lines.append("")
    return "\n".join(lines)
