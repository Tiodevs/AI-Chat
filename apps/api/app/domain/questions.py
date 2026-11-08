"""Regras da pergunta por HTTP: dono, marcador, cookie e baldes. Seções 7.1, 8.1 e 10.4.

Camada de domínio. `ConversationService` (`app/services/conversations.py`) usa quase tudo
daqui; os controladores de conversa e de cadastro leem o nome do cookie de convidado;
`app/schemas/conversations.py` usa o tamanho máximo da pergunta. Seções 10.3 e 11.4 também.
"""

from datetime import datetime, timedelta
from uuid import UUID

from app.domain.auth import (
    RateDecision,
    SessionCookie,
    retry_after_seconds,
    session_cookie_is_secure,
)

# Texto gravado no lugar de uma pergunta de orientação médica (seções 7.1 e 11.4). O histórico
# mostra o marcador, então o modelo nunca relê a pergunta de saúde.
HEALTH_MESSAGE_MARKER = "[health-related message not stored]"
# Tamanho máximo da pergunta (seção 12).
MAX_QUESTION_CHARS = 1000
# Cookie da chave de convidado: 30 dias, o mesmo prazo de retenção das conversas de convidado
# (seção 10.3).
GUEST_COOKIE_NAME = "atrium_guest"
GUEST_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
# Limites por hora da seção 10.4: 30 por chave de convidado, 60 por IP de convidado e 120 por
# membro. O membro não conta por IP.
QUESTION_WINDOW = timedelta(hours=1)
GUEST_QUESTION_KEY_LIMIT = 30
GUEST_QUESTION_IP_LIMIT = 60
MEMBER_QUESTION_LIMIT = 120
# Fluxo de diagnóstico, `GET /v1/diagnostics/stream`: 60 por hora por IP.
DIAGNOSTICS_WINDOW = timedelta(hours=1)
DIAGNOSTICS_IP_LIMIT = 60
# Prefixos dos baldes em `bucket_key`.
QUESTION_GUEST_KEY_PURPOSE = "question_guest"
QUESTION_GUEST_IP_PURPOSE = "question_ip"
QUESTION_MEMBER_PURPOSE = "question_member"
DIAGNOSTICS_IP_PURPOSE = "diagnostics_ip"


def stored_user_content(*, intent: str | None, text: str) -> str:
    """Orientação médica não fica gravada. O restante entra como foi enviado.

    O serviço chama na primeira transação, já com a intenção da classificação (seção 7.1).
    Sem classificação, com `intent` `None`, o texto também entra como foi enviado.
    """
    if intent == "medical_advice":
        return HEALTH_MESSAGE_MARKER
    return text


def owns_conversation(
    *,
    actor_user_id: UUID | None,
    actor_guest_key_id: UUID | None,
    owner_user_id: UUID | None,
    owner_guest_key_id: UUID | None,
) -> bool:
    """Diz se quem pede é dono da conversa: o mesmo usuário ou a mesma chave de convidado.

    Uma conversa anexada a uma conta no fim do cadastro guarda também a chave de convidado,
    então a chave antiga ainda a abre. A Etapa 15.1 do plano corrige isso.
    """
    if actor_user_id is not None and actor_user_id == owner_user_id:
        return True
    return actor_guest_key_id is not None and actor_guest_key_id == owner_guest_key_id


def guest_cookie(*, secret: str, app_env: str) -> SessionCookie:
    """Monta o cookie `atrium_guest`: os atributos do cookie de sessão, com 30 dias."""
    return SessionCookie(
        name=GUEST_COOKIE_NAME,
        value=secret,
        http_only=True,
        same_site="lax",
        secure=session_cookie_is_secure(app_env),
        path="/",
        max_age=GUEST_MAX_AGE_SECONDS,
    )


def guest_question_rate_decision(
    *,
    key_count: int,
    ip_count: int,
    now: datetime,
    window_start: datetime,
) -> RateDecision:
    """Decide o 429 do convidado: a chave passou de 30 ou o IP passou de 60 na hora.

    Os dois baldes usam a mesma janela. As contagens já incluem a pergunta atual.
    """
    retries: list[int] = []
    if key_count > GUEST_QUESTION_KEY_LIMIT:
        retries.append(retry_after_seconds(now, window_start, QUESTION_WINDOW))
    if ip_count > GUEST_QUESTION_IP_LIMIT:
        retries.append(retry_after_seconds(now, window_start, QUESTION_WINDOW))
    if not retries:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(limited=True, retry_after_seconds=max(retries))


def member_question_rate_decision(
    *,
    user_count: int,
    now: datetime,
    window_start: datetime,
) -> RateDecision:
    """Decide o 429 do membro: a 121ª pergunta na hora."""
    if user_count <= MEMBER_QUESTION_LIMIT:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(
        limited=True,
        retry_after_seconds=retry_after_seconds(now, window_start, QUESTION_WINDOW),
    )


def diagnostics_rate_decision(
    *,
    ip_count: int,
    now: datetime,
    window_start: datetime,
) -> RateDecision:
    """Decide o 429 do fluxo de diagnóstico: o 61º pedido do IP na hora."""
    if ip_count <= DIAGNOSTICS_IP_LIMIT:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(
        limited=True,
        retry_after_seconds=retry_after_seconds(now, window_start, DIAGNOSTICS_WINDOW),
    )
