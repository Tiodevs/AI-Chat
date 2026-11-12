"""Erros de domínio. O tratador HTTP mora em app.core.errors. Seção 6.2 do SDD.

Camada de domínio. Serviços, workflows e adaptadores levantam estes erros; o tratador único de
`app/core/errors.py` converte cada um no status HTTP e no envelope da seção 12, com `code`,
`message`, `request_id` e, quando existem, `retry_after_seconds`, `message_id` e
`field_errors`. Controladores não montam erro à mão. Cada classe diz o que deu errado; o
status de cada uma está em `_HTTP_STATUS`, no tratador.

`code` é um `ClassVar`: um atributo da classe, não da instância. Por isso o middleware lê
`Forbidden.code` sem criar o erro, e uma subclasse herda o código da mãe quando não declara o
próprio.
"""

from typing import ClassVar
from uuid import UUID


class DomainError(Exception):
    """Base dos erros que o tratador único converte no envelope da seção 12.

    `message` é o texto em português mostrado ao usuário, vindo de `app/prompts`.
    `field_errors` mapeia o nome do campo à mensagem do erro, para a tela marcar o campo. Um
    `DomainError` sem subclasse conhecida vira HTTP 500 com o código `domain_error`.
    """

    code: ClassVar[str] = "domain_error"

    def __init__(self, message: str, *, field_errors: dict[str, str] | None = None) -> None:
        """Guarda a mensagem e os erros de campo; a mensagem também vai para `Exception`."""
        super().__init__(message)
        self.message = message
        self.field_errors = field_errors


class NotFound(DomainError):
    """Recurso inexistente ou fora do alcance de quem pede. HTTP 404, `not_found`.

    O inspetor de qualidade também responde 404 para uma conversa de membro sem o
    consentimento de melhoria (seção 12).
    """

    code: ClassVar[str] = "not_found"


class Conflict(DomainError):
    """O estado atual impede o pedido. HTTP 409, `conflict`.

    Exemplos: e-mail já usado, feedback repetido, documento arquivado ou em processamento e
    pedido de titular já fechado.
    """

    code: ClassVar[str] = "conflict"


class DuplicateMessage(Conflict):
    """Reenvio do mesmo client_message_id. O envelope inclui message_id. Seção 7.1.

    `message_id` é o id da mensagem do visitante já gravada: o frontend recarrega a conversa
    em vez de mandar de novo, e o reenvio não chama o modelo. Herda o código `conflict` e o
    HTTP 409.
    """

    def __init__(self, message: str, *, message_id: UUID) -> None:
        """Guarda o id da mensagem já gravada, que vai no envelope do 409."""
        super().__init__(message)
        self.message_id = message_id


class Forbidden(DomainError):
    """Pessoa identificada, mas sem permissão. HTTP 403, `forbidden`.

    Exemplos: não é dona da conversa, não é admin, ou é um admin tentando se excluir. O
    `ApiGuardMiddleware` usa o código desta classe no 403 do segredo da borda (seção 10.3).
    """

    code: ClassVar[str] = "forbidden"


class BadOrigin(DomainError):
    """Origem diferente de WEB_ORIGIN. HTTP 403, código bad_origin. Seção 10.3.

    Nenhum código levanta esta exceção hoje: o `ApiGuardMiddleware` responde antes das rotas e
    usa só o `code`. O tratador também a mapeia para 403.
    """

    code: ClassVar[str] = "bad_origin"


class Unauthenticated(DomainError):
    """Sem sessão válida, ou login com credenciais erradas. HTTP 401, `unauthenticated`."""

    code: ClassVar[str] = "unauthenticated"


class ValidationFailed(DomainError):
    """Dados que não passam nas regras, ou um passo fora de ordem. HTTP 422.

    O código é `validation_error`, o mesmo do corpo que falha no schema. Um erro de campo traz
    `field_errors`, com uma mensagem por campo; um passo fora de ordem traz só a `message`.
    """

    code: ClassVar[str] = "validation_error"


class RateLimited(DomainError):
    """Limite de taxa estourado (seção 10.4). HTTP 429, `rate_limited`."""

    code: ClassVar[str] = "rate_limited"

    def __init__(self, message: str, *, retry_after_seconds: int) -> None:
        """Guarda a espera, que vai em `retry_after_seconds` no envelope do 429."""
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class BudgetExceeded(DomainError):
    """Orçamento estourado. O envelope usa o código degraded e HTTP 503.

    Só o cadastro por chat levanta este erro, antes do turno (seção 7.2). A pergunta não o
    levanta: ela grava o desfecho `degraded` e responde com o texto fixo de indisponibilidade.
    """

    code: ClassVar[str] = "degraded"


class ProviderUnavailable(DomainError):
    """O provedor de IA falhou ou não está configurado. HTTP 503, `provider_unavailable`.

    Os adaptadores de chat levantam este erro. O pipeline de perguntas o troca pelo desfecho
    `error`, e o cadastro por chat o levanta de novo com a mensagem `REGISTRATION_UNAVAILABLE`.
    """

    code: ClassVar[str] = "provider_unavailable"


class CircuitOpen(ProviderUnavailable):
    """O circuito do modelo está aberto. O pipeline degrada sem chamar o gerador.

    `GeminiChatProvider` levanta este erro depois de 5 falhas seguidas, por 60 segundos
    (seção 7.1). É uma subclasse de `ProviderUnavailable`, então quem trata a mãe também trata
    esta; o `QaWorkflow` a captura antes e grava `degraded` em vez de `error`.
    """


class HandoffNotOffered(Conflict):
    """A última resposta do assistente não permite chamar a equipe (seção 29.4). HTTP 409."""

    code: ClassVar[str] = "handoff_not_offered"


class HandoffActive(Conflict):
    """Já há atendimento ativo do visitante, ou a pergunta chegou durante um. HTTP 409.

    O envelope leva `handoff_id` e `conversation_id`, para a visão abrir o atendimento certo
    (seção 29.10).
    """

    code: ClassVar[str] = "handoff_active"

    def __init__(self, message: str, *, handoff_id: UUID, conversation_id: UUID) -> None:
        """Guarda os ids que vão no envelope do 409."""
        super().__init__(message)
        self.handoff_id = handoff_id
        self.conversation_id = conversation_id


class HandoffUnavailable(DomainError):
    """A fila está cheia, ninguém está presente ou o serviço está desligado. HTTP 503.

    O envelope leva `availability`, com `busy`, `closed` ou `disabled` (seção 29.4).
    """

    code: ClassVar[str] = "handoff_unavailable"

    def __init__(self, message: str, *, availability: str) -> None:
        """Guarda o status da disponibilidade que vai no envelope."""
        super().__init__(message)
        self.availability = availability


class HandoffBlocked(Forbidden):
    """Bloqueio de 24 horas depois de um encerramento por abuso. HTTP 403."""

    code: ClassVar[str] = "handoff_blocked"


class HandoffClosed(Conflict):
    """Mensagem ou ação num atendimento encerrado. HTTP 409."""

    code: ClassVar[str] = "handoff_closed"


class HandoffTaken(Conflict):
    """Outra pessoa assumiu primeiro (seção 29.5). HTTP 409."""

    code: ClassVar[str] = "handoff_taken"


class AttendantAtCapacity(Conflict):
    """A pessoa já tem 3 atendimentos. HTTP 409."""

    code: ClassVar[str] = "attendant_at_capacity"


class AcknowledgementRequired(Forbidden):
    """Falta o aceite do compromisso de confidencialidade vigente (seção 29.3). HTTP 403."""

    code: ClassVar[str] = "acknowledgement_required"
