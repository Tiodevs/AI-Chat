"""Chat por regras do modo `demo`. Seções 17 e 21.1 do SDD.

Sem modelo e sem rede. Serve à e2e da CI, que percorre as jornadas com a API de verdade, e à
demonstração local sem chave. As regras são poucas e previsíveis:

- Classificação: palavras de sintoma, dose ou remédio viram `medical_advice`; tempo e clima
  viram `other`; o resto é `public_info`. A pergunta reescrita é a própria pergunta.
- Geração: a primeira frase do bloco de contexto de melhor posição, com a citação dele.
  Como o texto vem do contexto, a conferência de fundamentação passa.
- Cadastro: o passo atual decide o campo; "pular" e parecidos pulam um opcional.
- Frases do cadastro: indisponível, então valem as perguntas fixas de `app/prompts`.

Nunca roda em `development` nem em `production` (`app.core.config`).

Implementa a porta `ChatProvider` (ADR-014). Quem usa: `build_chat_provider` com
`APP_AI_ADAPTER=demo`. As saídas passam pelas mesmas guardas das do Gemini: lista de permissão
do cadastro e conferência de citação e de telefone. As regras leem os textos montados pelos
workflows, então dependem de dois formatos: o bloco `contexto_nao_confiavel` de
`app.prompts.qa` e a linha "Passo atual" do nó `extract` do cadastro.
"""

import re
from collections.abc import AsyncIterator

from app.adapters.lexical_embedding import tokens
from app.domain.errors import ProviderUnavailable
from app.domain.fields import SET_FIELDS_TOOL_NAME, VISIT_REASONS, VISITOR_TYPES
from app.ports.chat import Message, ModelT, RunContext, Tool, ToolResult
from app.prompts.qa import CHAT_UNAVAILABLE

# Palavras, já sem acento e em minúsculas como `tokens` as devolve, que marcam orientação
# médica. Como "tomar" está na lista, "Posso tomar café na lanchonete?" também vira
# `medical_advice` neste modo.
_MEDICAL = frozenset(
    {
        "dor", "dores", "sintoma", "sintomas", "remedio", "remedios", "medicamento",
        "medicamentos", "dose", "doses", "ibuprofeno", "paracetamol", "dipirona", "febre",
        "diagnostico", "tomar", "tosse", "sangramento", "receita",
    }
)
# Palavras que marcam um assunto fora do hospital.
_OFF_TOPIC = frozenset({"clima", "previsao", "chover", "chuva", "futebol", "temperatura"})
# "Tempo" só é fora de tema perto de um dia: "ao mesmo tempo" é uma pergunta de visita.
_WEATHER_DAYS = frozenset({"amanha", "hoje", "semana", "fim"})
# Palavras que, num passo opcional, valem como "pular este campo".
_SKIP = frozenset(
    {"pular", "pula", "pulo", "nao", "sem", "nenhum", "nenhuma", "prefiro", "passar", "passo"}
)
# O bloco que `untrusted_block` monta: o índice e o conteúdo entre as tags.
_BLOCK = re.compile(
    r'<contexto_nao_confiavel indice="(?P<index>\d+)"[^>]*>\n'
    r"(?P<content>.*?)\n</contexto_nao_confiavel>",
    re.DOTALL,
)
# A linha que o nó `extract` acrescenta às regras da extração.
_STEP = re.compile(r"Passo atual: (?P<step>[a-z_]+)\.")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Palavras que escolhem um valor dos enums `visitor_type` e `visit_reason` (seção 8.5).
_VISITOR_WORDS = {
    "patient": ("paciente",),
    "visitor": ("visitante", "visita", "visitar"),
    "caregiver": ("acompanhante", "cuidador", "cuidadora", "acompanho"),
}
_REASON_WORDS = {
    "visiting_someone": ("visitar", "visita", "internado", "internada"),
    "own_appointment": ("consulta",),
    "exam_or_test": ("exame", "exames", "teste"),
    "accompanying_someone": ("acompanhar", "acompanhando", "acompanho"),
    "administrative": ("administrativo", "documento", "cobranca", "boleto"),
}


class DemoChatProvider:
    """Respostas por regras para as três operações da porta de chat. Não conta tokens."""

    model_name = "demo-rules"

    async def complete_structured(
        self,
        messages: list[Message],
        schema: type[ModelT],
        run: RunContext,
    ) -> ModelT:
        """Responde só à classificação da pergunta, reconhecida pelos campos do schema.

        A pergunta reescrita é a própria pergunta, e a confiança fixa de 0,9 passa do portão
        de 0,6 (seção 7.1). Qualquer outro schema levanta `ProviderUnavailable`.
        """
        fields = set(schema.model_fields)
        if {"standalone_question", "intent", "confidence"} <= fields:
            question = _last_user(messages)
            return schema.model_validate(
                {"standalone_question": question, "intent": _intent(question), "confidence": 0.9}
            )
        # Frases do cadastro e juízes de avaliação ficam com o texto fixo de quem chama.
        raise ProviderUnavailable(CHAT_UNAVAILABLE)

    async def complete_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        run: RunContext,
    ) -> ToolResult:
        """Responde à extração do cadastro chamando `set_fields` com o campo do passo atual."""
        if not any(tool.name == SET_FIELDS_TOOL_NAME for tool in tools):
            raise ProviderUnavailable(CHAT_UNAVAILABLE)
        step = _step(messages)
        text = _last_user(messages).strip()
        return ToolResult(name=SET_FIELDS_TOOL_NAME, arguments=_registration_fields(step, text))

    def stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]:
        """Transmite a resposta palavra a palavra, como um fluxo de tokens.

        Cada pedaço leva o espaço que vinha depois da palavra, então o texto juntado é igual
        ao original. Sem bloco de contexto, levanta `ProviderUnavailable`.
        """

        async def iterate() -> AsyncIterator[str]:
            answer = _answer(_last_user(messages))
            if answer is None:
                raise ProviderUnavailable(CHAT_UNAVAILABLE)
            words = answer.split(" ")
            for position, word in enumerate(words):
                yield word if position == len(words) - 1 else f"{word} "

        return iterate()


def _last_user(messages: list[Message]) -> str:
    """O texto da última mensagem do visitante, ou vazio."""
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return ""


def _step(messages: list[Message]) -> str:
    """O passo do cadastro lido da linha "Passo atual" das mensagens de sistema, ou vazio."""
    for message in messages:
        if message.role == "system":
            found = _STEP.search(message.content)
            if found:
                return found.group("step")
    return ""


def _intent(question: str) -> str:
    """A intenção pela regra do cabeçalho. Orientação médica vem antes de fora de tema."""
    words = set(tokens(question))
    if words & _MEDICAL:
        return "medical_advice"
    if words & _OFF_TOPIC or ("tempo" in words and words & _WEATHER_DAYS):
        return "other"
    return "public_info"


def _answer(prompt: str) -> str | None:
    """A primeira frase útil do primeiro bloco, com a citação do bloco.

    O primeiro bloco é o de melhor posição na busca. Linhas vazias e títulos Markdown são
    pulados, e os marcadores de lista saem. A frase termina no primeiro `.`, `!` ou `?`
    seguido de espaço.
    """
    block = _BLOCK.search(prompt)
    if block is None:
        return None
    for line in block.group("content").splitlines():
        sentence = line.strip().lstrip("-*").strip()
        if not sentence or sentence.startswith("#"):
            continue
        first = re.split(r"(?<=[.!?])\s", sentence, maxsplit=1)[0].strip()
        if first:
            return f"{first} [{block.group('index')}]"
    return None


def _registration_fields(step: str, text: str) -> dict[str, object]:
    """Os argumentos de `set_fields` para a mensagem, pelo passo atual.

    Num passo opcional, uma palavra de `_SKIP` pula o campo. Nome e telefone vão como vieram,
    e o e-mail é o primeiro endereço achado no texto; a validação do domínio julga os três.
    Tipo de visitante e motivo da visita saem das tabelas de palavras. Num passo que não pede
    campo, só um e-mail no texto é lido.
    """
    words = set(tokens(text))
    email = _EMAIL.search(text)
    if step in {"phone", "visitor_type", "visit_reason"} and words & _SKIP:
        return {"skip_current": True}
    if step == "full_name":
        return {"full_name": text}
    if step == "email":
        return {"email": email.group(0) if email else text}
    if step == "phone":
        return {"phone": text}
    if step == "visitor_type":
        return _choice("visitor_type", words, _VISITOR_WORDS, VISITOR_TYPES)
    if step == "visit_reason":
        return _choice("visit_reason", words, _REASON_WORDS, VISIT_REASONS)
    return {"email": email.group(0)} if email else {}


def _choice(
    field: str,
    words: set[str],
    table: dict[str, tuple[str, ...]],
    allowed: tuple[str, ...],
) -> dict[str, object]:
    """O primeiro valor permitido cujas palavras aparecem na mensagem; sem nenhum, pula."""
    for value, hints in table.items():
        if value in allowed and words & set(hints):
            return {field: value}
    return {"skip_current": True}
