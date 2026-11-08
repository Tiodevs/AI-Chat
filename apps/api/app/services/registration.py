"""Cadastro por chat e por formulário. Os dois chamam a mesma conclusão. Seção 7.2.

Camada de serviço. `controllers/registration.py` chama `RegistrationService`, montado por
pedido em `core/container.py:get_registration_service` com o `RegistrationWorkflow` do
`AiRuntime` (o grafo do LangGraph compilado uma vez por processo), o hasher argon2id e o
orçamento `PostgresTokenBudget`. Usa a máquina de estados de `domain/registration.py`, as
regras de campo de `domain/fields.py`, as cópias fixas de `prompts/registration.py` e os
repositórios de sessão de cadastro, usuário, consentimento, sessão de autenticação,
conversa e limite de taxa.

O modelo nunca decide a transição, o `role`, o consentimento nem a senha: o workflow só
extrai campos e escreve a frase, e `decide_next`, no domínio, escolhe o próximo passo. O
caminho do chat é `start`, `message` (e `patch_fields`), `set_password`, `review` e
`accept`. O formulário é `submit_form`, num pedido só. Os dois terminam em `_create_member`.

Padrões que se repetem:

- Um erro encontrado dentro da transação é devolvido, e quem chama o levanta depois que o
  bloco fecha. Assim a transação confirma o que precisa ficar, como a sessão vencida
  marcada `abandoned`, antes de o erro virar resposta.
- `_save` trava a linha da sessão (`SELECT ... FOR UPDATE`) e compara só o `status`.
  Campos e transcrição vêm do registro lido antes da chamada ao modelo, então duas
  gravações simultâneas podem apagar uma à outra. A Etapa 13.3 acrescenta uma versão.
- Métricas: `atrium_registration_events` com `started`, `password_set`, `completed` e
  `abandoned` aqui, e `extracted` no workflow (seção 18.3). `optional_skipped` não é contado
  em lugar nenhum.
"""

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.session_secret import new_session_secret
from app.core.metrics import REGISTRATION_EVENTS
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import (
    SESSION_MAX_AGE_SECONDS,
    SessionCookie,
    bucket_key,
    clean_user_agent,
    hash_session_secret,
    session_cookie,
)
from app.domain.errors import (
    BudgetExceeded,
    Conflict,
    DomainError,
    NotFound,
    ProviderUnavailable,
    RateLimited,
    ValidationFailed,
)
from app.domain.fields import FieldIssue, password_is_acceptable, validate_field
from app.domain.legal import LEGAL_DOCUMENT_VERSION, needs_legal_acceptance
from app.domain.profile import Profile
from app.domain.registration import (
    MEMBER_ROLE,
    REGISTRATION_IP_PURPOSE,
    Acceptance,
    ConsentSource,
    FieldSet,
    FormValues,
    Machine,
    MemberDraft,
    Path,
    PublicFields,
    Status,
    Step,
    TranscriptItem,
    accept_review,
    accepts_message,
    apply_edits,
    collect_form,
    completed_document,
    draft_member,
    dump_transcript,
    fields_document,
    load_transcript,
    machine_from_document,
    mark_password_set,
    new_machine,
    public_fields,
    registration_deadline,
    registration_rate_decision,
    registration_window_start,
    reject_review,
    session_is_expired,
    with_issue,
)
from app.ports.budget import TokenBudget
from app.ports.clock import Clock
from app.ports.password_hasher import PasswordHasher
from app.prompts.registration import (
    COMPLETION_FAILED,
    EMAIL_TAKEN,
    EXPIRED,
    GREETING,
    NOT_FOUND,
    RATE_LIMITED,
    REGISTRATION_UNAVAILABLE,
    WRONG_STEP,
    message_for,
    prompt_for,
    review_prompt,
)
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.consents import ConsentRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.rate_limits import RateLimitRepository
from app.repositories.registration import RegistrationRecord, RegistrationRepository
from app.repositories.users import UserRepository
from app.workflows.registration import RegistrationWorkflow

# Os dois caminhos de `registration_sessions.path` (seção 8.1).
PathName = Literal["chat", "form"]


@dataclass(frozen=True, slots=True)
class SessionView:
    """O que cada pedido da sessão de cadastro devolve (seção 12).

    `fields` são os campos entendidos, `field_errors` as mensagens em português por campo,
    `next_step` o passo que a interface mostra (a senha tem tela própria) e `prompt` a fala
    do assistente. `messages` é a transcrição, que não tem campo de senha.
    """

    id: UUID
    status: str
    path: PathName
    fields: PublicFields
    field_errors: dict[str, str]
    next_step: str
    prompt: str
    messages: tuple[TranscriptItem, ...]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class Completion:
    """O membro criado, ou reencontrado num aceite repetido, e o cookie da sessão nova."""

    profile: Profile
    cookie: SessionCookie


@dataclass(frozen=True, slots=True)
class FormInput:
    """O formulário inteiro num pedido, com senha e aceites.

    `session_id` é opcional: liga o envio a um cadastro que começou no chat.
    """

    session_id: UUID | None
    full_name: str
    email: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    password: str
    accept_terms: bool
    document_version: str
    age_18_plus: bool
    profile_personalization: bool
    quality_improvement: bool


class RegistrationService:
    """Casos de uso do cadastro (seção 7.2). Sem estado além das dependências.

    `hmac_key` é a `RATE_LIMIT_HMAC_KEY` do balde de 20 por hora por IP. `app_env` decide o
    `Secure` do cookie. `workflow` é o grafo do cadastro e `budget`, o orçamento diário
    compartilhado com as perguntas.
    """

    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        hasher: PasswordHasher,
        hmac_key: str,
        app_env: str,
        workflow: RegistrationWorkflow,
        budget: TokenBudget,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hasher = hasher
        self._hmac_key = hmac_key
        self._app_env = app_env
        self._workflow = workflow
        self._budget = budget

    async def start(self) -> SessionView:
        """Começa um cadastro por chat em `collecting_required`, válido por 24 horas.

        A saudação é cópia fixa, então a primeira tela não depende do Gemini (seção 12).
        Uma transação grava a sessão com a saudação na transcrição. Conta `started` com o
        caminho `chat`. Não tem limite de taxa.
        """
        now = self._clock.now()
        machine = new_machine()
        transcript = (TranscriptItem(role="assistant", text=GREETING, created_at=now),)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            record = await RegistrationRepository(session).insert(
                session_id=uuid4(),
                status=machine.status.value,
                path=Path.CHAT.value,
                fields=fields_document(machine),
                password_hash=None,
                transcript=dump_transcript(transcript),
                user_id=None,
                expires_at=registration_deadline(now),
            )
        REGISTRATION_EVENTS.labels(event="started", path=Path.CHAT.value).inc()
        return _view(record, machine, GREETING)

    async def get(self, session_id: UUID) -> SessionView:
        """Estado da sessão para a tela retomar o cadastro.

        Inexistente responde 404. Vencida é marcada `abandoned`, e o pedido responde 422
        com `EXPIRED`. O `prompt` é a última fala do assistente na transcrição.
        """
        record, machine = await self._open(session_id)
        return _view(record, machine, _stored_prompt(record, machine))

    async def message(
        self,
        session_id: UUID,
        text: str,
        *,
        request_id: str,
        client_ip: str,
    ) -> SessionView:
        """Um turno do chat: extrai campos da mensagem, decide o passo e responde.

        1. Conta o pedido no balde de 20 por hora por IP (429).
        2. Abre a sessão (404, ou 422 se venceu).
        3. Só a coleta de campos aceita mensagem. Senha, revisão e aceite têm rotas
           próprias, então qualquer outro estado responde 422.
        4. Com o orçamento do dia estourado, responde 503 com o código `degraded`, sem
           chamar o Gemini e sem gravar a mensagem na transcrição (seção 7.2).
        5. Roda o grafo `extract`, `decide_next` e `phrase` fora de transação. O callback
           `email_taken` abre uma leitura curta entre as duas chamadas ao modelo. Provedor
           indisponível responde 503 e a tela oferece o formulário.
        6. Soma os tokens da extração e da frase em `token_usage_days`.
        7. Acrescenta a mensagem do visitante e a resposta à transcrição e grava com
           `_save`, que trava a linha e confere o status.

        O texto do visitante fica na transcrição até a conclusão ou o abandono. A senha
        nunca passa por aqui.
        """
        # 1.
        await self._limit(client_ip)
        # 2.
        record, machine = await self._open(session_id)
        # 3.
        if not accepts_message(machine):
            raise ValidationFailed(WRONG_STEP)
        # 4. Seção 7.1: com o teto estourado, o cadastro por chat oferece só o formulário.
        if await self._budget.exceeded():
            raise BudgetExceeded(REGISTRATION_UNAVAILABLE)
        # 5. Chamadas ao Gemini, sem transação aberta (seção 6.4).
        try:
            result = await self._workflow.turn(
                machine,
                text,
                request_id=request_id,
                email_taken=self._email_taken,
            )
        except ProviderUnavailable:
            raise ProviderUnavailable(REGISTRATION_UNAVAILABLE) from None
        # 6. Uma falha do provedor na extração sobe antes daqui, sem somar os tokens dela.
        # Na frase, a falha cai na pergunta modelo e o uso entra.
        await self._budget.record(result.input_tokens, result.output_tokens)
        # 7.
        now = self._clock.now()
        transcript = (
            *load_transcript(record.transcript),
            TranscriptItem(role="user", text=text, created_at=now),
            TranscriptItem(role="assistant", text=result.prompt, created_at=now),
        )
        saved = await self._save(record, result.machine, transcript, record.password_hash)
        return _view(saved, result.machine, result.prompt)

    async def patch_fields(self, session_id: UUID, edits: dict[str, str | None]) -> SessionView:
        """Edição direta no cartão de resumo, com as regras do formulário (seção 12).

        Não chama o modelo, não consulta o orçamento e não conta no balde. Recusa uma sessão
        concluída ou abandonada (422). Um campo mudado na revisão, no aceite ou na senha
        volta a sessão para a coleta, e o domínio a traz de volta ao passo certo. A
        transcrição e o hash da senha continuam os mesmos.
        """
        record, machine = await self._open(session_id)
        if machine.status in (Status.COMPLETED, Status.ABANDONED):
            raise ValidationFailed(WRONG_STEP)
        updated = await self._edit(machine, edits)
        prompt = _step_prompt(updated)
        transcript = load_transcript(record.transcript)
        saved = await self._save(record, updated, transcript, record.password_hash)
        return _view(saved, updated, prompt)

    async def set_password(self, session_id: UUID, password: str, *, client_ip: str) -> SessionView:
        """Grava o hash da senha e avança para a revisão.

        1. Conta no mesmo balde das mensagens (429) e abre a sessão (404 ou 422).
        2. Só vale em `awaiting_password` (422 fora dele).
        3. Uma senha fora de 12 a 72 caracteres não é hasheada: grava o erro de campo e
           devolve o mesmo passo, com resposta 200.
        4. Calcula o argon2id fora de transação, marca a senha no domínio, conta
           `password_set` e grava só o hash.

        A senha não vira mensagem: a transcrição recebe só a fala seguinte do assistente
        (seções 7.2 e 8.1).
        """
        # 1.
        await self._limit(client_ip)
        record, machine = await self._open(session_id)
        # 2.
        if machine.status != Status.AWAITING_PASSWORD:
            raise ValidationFailed(WRONG_STEP)
        # 3.
        if not password_is_acceptable(password):
            invalid = replace(machine, field_errors=(FieldIssue("password", "invalid"),))
            saved = await self._save(
                record,
                invalid,
                load_transcript(record.transcript),
                record.password_hash,
            )
            prompt = prompt_for(invalid.next_step.value, correcting=False)
            return _view(saved, invalid, prompt)
        # 4. O argon2 roda no loop de eventos (Etapa 13.1).
        digest = self._hasher.hash_password(password)
        updated = mark_password_set(machine)
        if updated is None:
            raise ValidationFailed(WRONG_STEP)
        # O contador sobe antes de `_save`: um `_save` recusado não o desfaz.
        REGISTRATION_EVENTS.labels(event="password_set", path=record.path).inc()
        prompt = _step_prompt(updated)
        now = self._clock.now()
        transcript = (
            *load_transcript(record.transcript),
            TranscriptItem(role="assistant", text=prompt, created_at=now),
        )
        saved = await self._save(record, updated, transcript, digest)
        return _view(saved, updated, prompt)

    async def review(self, session_id: UUID, *, accept: bool) -> SessionView:
        """Confirma o resumo ou volta para corrigir um campo.

        `accept` leva a `awaiting_acceptance`. Recusar volta para `collecting_required` no
        modo de correção, que pergunta o que mudar. Fora de `awaiting_review`, 422. A
        transcrição recebe a fala do passo seguinte.
        """
        record, machine = await self._open(session_id)
        updated = accept_review(machine) if accept else reject_review(machine)
        if updated is None:
            raise ValidationFailed(WRONG_STEP)
        prompt = _step_prompt(updated)
        now = self._clock.now()
        transcript = (
            *load_transcript(record.transcript),
            TranscriptItem(role="assistant", text=prompt, created_at=now),
        )
        saved = await self._save(record, updated, transcript, record.password_hash)
        return _view(saved, updated, prompt)

    async def accept(
        self,
        session_id: UUID,
        acceptance: Acceptance,
        *,
        user_agent: str,
        guest_secret: str | None,
    ) -> Completion:
        """Registra os aceites e conclui o cadastro por chat (seção 7.2).

        A conclusão roda numa transação em `_accept_locked`. A chave de idempotência é o id
        da sessão: um aceite repetido devolve o mesmo usuário com uma sessão de autenticação
        nova. Um e-mail que outra pessoa cadastrou no meio tempo esbarra no índice único de
        `users.email` e responde 409 com `field_errors.email`. Devolve o perfil e o cookie,
        que o controlador define.
        """
        now = self._clock.now()
        try:
            error, result = await self._accept_locked(
                session_id,
                acceptance,
                user_agent=user_agent,
                guest_secret=guest_secret,
                now=now,
            )
        except IntegrityError:
            raise Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN}) from None
        if error is not None:
            raise error
        if result is None:
            raise NotFound(NOT_FOUND)
        return result

    async def submit_form(
        self,
        form: FormInput,
        *,
        user_agent: str,
        guest_secret: str | None,
        client_ip: str,
    ) -> Completion:
        """Formulário completo. Usa a mesma conclusão do chat (seção 7.2).

        1. Conta no balde de 20 por hora por IP, o mesmo do chat (429).
        2. Com `session_id` de uma sessão já concluída, devolve o mesmo usuário com uma
           sessão nova e ignora o resto do formulário. Sessão inexistente ou vencida
           responde 404 ou 422.
        3. Valida o formulário inteiro no domínio: erros de campo respondem 422 sem gravar.
        4. Um e-mail já cadastrado responde 409 (seção 12).
        5. Calcula o argon2id fora de transação.
        6. Conclui numa transação: sem sessão, `_finish_new_form`; com sessão,
           `_finish_form_session`.

        O e-mail é conferido de novo dentro da transação, e o índice único de `users.email`
        é a última barreira.
        """
        # 1.
        await self._limit(client_ip)
        # 2. Idempotência pela sessão de cadastro.
        if form.session_id is not None:
            existing, _machine = await self._open(form.session_id)
            if existing.status == Status.COMPLETED.value and existing.user_id is not None:
                return await self._reissue_standalone(existing.user_id, user_agent)
        # 3.
        draft = _draft_from_form(form)
        # 4.
        if await self._email_taken(draft.email):
            raise Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN})
        # 5. O argon2 roda no loop de eventos (Etapa 13.1).
        digest = self._hasher.hash_password(form.password)
        now = self._clock.now()
        # 6.
        if form.session_id is None:
            return await self._finish_new_form(
                draft,
                digest,
                user_agent=user_agent,
                guest_secret=guest_secret,
                now=now,
            )
        return await self._finish_form_session(
            form.session_id,
            draft,
            digest,
            user_agent=user_agent,
            guest_secret=guest_secret,
            now=now,
        )

    async def _accept_locked(
        self,
        session_id: UUID,
        acceptance: Acceptance,
        *,
        user_agent: str,
        guest_secret: str | None,
        now: datetime,
    ) -> tuple[DomainError | None, Completion | None]:
        """A transação da conclusão por chat. Devolve `(erro, conclusão)`.

        Trava a linha da sessão, então dois aceites simultâneos não criam dois usuários: o
        segundo espera, encontra a sessão `completed` e recebe a sessão de autenticação
        reemitida. Inexistente dá 404; vencida é marcada `abandoned` e dá 422; fora de
        `awaiting_acceptance`, 422. O erro é devolvido, não levantado, para a transação
        confirmar o abandono.
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            current = await RegistrationRepository(session).lock(session_id)
            if current is None:
                return NotFound(NOT_FOUND), None
            if current.status == Status.COMPLETED.value and current.user_id is not None:
                return None, await self._reissue(session, current.user_id, user_agent, now)
            closed = await _close_if_needed(session, current, now)
            if closed is not None:
                return closed, None
            if current.status != Status.AWAITING_ACCEPTANCE.value:
                return ValidationFailed(WRONG_STEP), None
            machine = machine_from_document(
                current.status,
                current.fields,
                password_set=current.password_hash is not None,
            )
            return await self._finish_record(
                session,
                current,
                acceptance=acceptance,
                source=ConsentSource.CHAT.value,
                password_hash=current.password_hash,
                fields=machine.fields,
                user_agent=user_agent,
                guest_secret=guest_secret,
                now=now,
            )
        # Nunca roda. `UnitOfWork.__aexit__` declara `bool`, o mypy supõe que o bloco pode
        # engolir a exceção e exige uma saída depois dele.
        raise RuntimeError("registration session")

    async def _finish_record(
        self,
        session: AsyncSession,
        current: RegistrationRecord,
        *,
        acceptance: Acceptance,
        source: str,
        password_hash: str | None,
        fields: FieldSet,
        user_agent: str,
        guest_secret: str | None,
        now: datetime,
    ) -> tuple[DomainError | None, Completion | None]:
        """Os passos 1 a 6 da conclusão da seção 7.2, na transação de quem chama.

        1. `draft_member` exige nome, e-mail, senha, os Termos na versão vigente e a
           maioridade, e descarta `visitor_type` e `visit_reason` sem a personalização.
           Falta ou erro responde 422 com `field_errors`, sem gravar usuário.
        2. E-mail já cadastrado responde 409.
        3. a 5. `_create_member` grava o membro, os consentimentos, anexa as conversas de
           convidado e abre a sessão de autenticação.
        6. Marca a sessão `completed`, apaga a transcrição e o hash da senha.

        Devolve `(erro, conclusão)`, como `_accept_locked`.
        """
        # 1. As regras da conclusão moram no domínio.
        draft = draft_member(
            fields,
            acceptance,
            expected_version=LEGAL_DOCUMENT_VERSION,
            password_ready=password_hash is not None,
        )
        if not isinstance(draft, MemberDraft):
            return ValidationFailed(COMPLETION_FAILED, field_errors=_messages(draft)), None
        # Já coberto por `password_ready`; aqui o tipo do hash fica estreito para o mypy.
        if password_hash is None:
            missing = (FieldIssue("password", "required"),)
            return ValidationFailed(COMPLETION_FAILED, field_errors=_messages(missing)), None
        # 2.
        if await UserRepository(session).get_by_email(draft.email) is not None:
            return Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN}), None
        # 3 a 5.
        result = await self._create_member(
            session,
            draft=draft,
            password_hash=password_hash,
            source=source,
            user_agent=user_agent,
            guest_secret=guest_secret,
            now=now,
        )
        # 6.
        await RegistrationRepository(session).save(_completed(current, draft, result.profile.id))
        return None, result

    async def _finish_new_form(
        self,
        draft: MemberDraft,
        password_hash: str,
        *,
        user_agent: str,
        guest_secret: str | None,
        now: datetime,
    ) -> Completion:
        """Conclui um formulário sem sessão de cadastro, numa transação.

        Confere o e-mail de novo (409), cria o membro com `source = form` e grava uma sessão
        de cadastro já `completed`, no caminho `form`, sem transcrição nem hash. É essa
        linha que o funil do admin conta (`repositories/insights.py:funnel`). Este caminho
        não incrementa `atrium_registration_events`, nem `started` nem `completed`.
        """
        error: DomainError | None = None
        result: Completion | None = None
        try:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                if await UserRepository(session).get_by_email(draft.email) is not None:
                    error = Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN})
                else:
                    result = await self._create_member(
                        session,
                        draft=draft,
                        password_hash=password_hash,
                        source=ConsentSource.FORM.value,
                        user_agent=user_agent,
                        guest_secret=guest_secret,
                        now=now,
                    )
                    await RegistrationRepository(session).insert(
                        session_id=uuid4(),
                        status=Status.COMPLETED.value,
                        path=Path.FORM.value,
                        fields=completed_document(draft),
                        password_hash=None,
                        transcript=[],
                        user_id=result.profile.id,
                        expires_at=registration_deadline(now),
                    )
        except IntegrityError:
            # Outro cadastro com o mesmo e-mail confirmou primeiro.
            raise Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN}) from None
        if error is not None:
            raise error
        if result is None:
            raise NotFound(NOT_FOUND)
        return result

    async def _finish_form_session(
        self,
        session_id: UUID,
        draft: MemberDraft,
        password_hash: str,
        *,
        user_agent: str,
        guest_secret: str | None,
        now: datetime,
    ) -> Completion:
        """Conclui pelo formulário um cadastro que começou no chat, numa transação.

        Trava a sessão: concluída, reemite a sessão de autenticação; vencida, marca
        `abandoned` e responde 422; e-mail tomado, 409. Senão cria o membro com
        `source = form` e marca a sessão `completed` com os dados do formulário. A sessão
        mantém o caminho de origem, então a métrica `completed` e o funil a contam como
        `chat`. Qualquer passo em que a sessão estava serve: o formulário traz tudo.
        """
        error: DomainError | None = None
        result: Completion | None = None
        try:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                current = await RegistrationRepository(session).lock(session_id)
                if current is None:
                    error = NotFound(NOT_FOUND)
                elif current.status == Status.COMPLETED.value and current.user_id is not None:
                    result = await self._reissue(session, current.user_id, user_agent, now)
                else:
                    closed = await _close_if_needed(session, current, now)
                    if closed is not None:
                        error = closed
                    elif await UserRepository(session).get_by_email(draft.email) is not None:
                        error = Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN})
                    else:
                        result = await self._create_member(
                            session,
                            draft=draft,
                            password_hash=password_hash,
                            source=ConsentSource.FORM.value,
                            user_agent=user_agent,
                            guest_secret=guest_secret,
                            now=now,
                        )
                        await RegistrationRepository(session).save(
                            _completed(current, draft, result.profile.id)
                        )
        except IntegrityError:
            raise Conflict(EMAIL_TAKEN, field_errors={"email": EMAIL_TAKEN}) from None
        if error is not None:
            raise error
        if result is None:
            raise NotFound(NOT_FOUND)
        return result

    async def _create_member(
        self,
        session: AsyncSession,
        *,
        draft: MemberDraft,
        password_hash: str,
        source: str,
        user_agent: str,
        guest_secret: str | None,
        now: datetime,
    ) -> Completion:
        """Os passos 3 a 5 da conclusão (seção 7.2), na transação de quem chama.

        1. Insere o usuário com `role = member`, fixo no código (seção 10.5). O índice
           único de `users.email` pode levantar `IntegrityError` aqui.
        2. Grava os consentimentos do rascunho (Termos, maioridade e os opcionais aceitos)
           com a versão vigente e a origem, `chat` ou `form`.
        3. Anexa ao membro as conversas da chave de convidado do cookie atual. Elas mantêm o
           `guest_key_id`, e a chave antiga continua abrindo-as (Etapa 15.1).
        4. Abre a sessão de autenticação e prepara o cookie.

        O perfil volta com `needs_legal_acceptance` falso, porque o aceite acabou de
        acontecer.
        """
        # 1.
        user_id = await UserRepository(session).insert(
            email=draft.email,
            password_hash=password_hash,
            full_name=draft.full_name,
            role=MEMBER_ROLE,
            now=now,
            phone=draft.phone,
            visitor_type=draft.visitor_type,
            visit_reason=draft.visit_reason,
        )
        # 2.
        await ConsentRepository(session).insert_grants(
            user_id=user_id,
            grants=draft.consents,
            source=source,
            granted_at=now,
        )
        # 3.
        guest_id = await _guest_id(session, guest_secret)
        if guest_id is not None:
            await ConversationRepository(session).attach_to_user(
                guest_key_id=guest_id,
                user_id=user_id,
            )
        # 4.
        return Completion(
            profile=Profile(
                id=user_id,
                email=draft.email,
                full_name=draft.full_name,
                phone=draft.phone,
                visitor_type=draft.visitor_type,
                visit_reason=draft.visit_reason,
                role=MEMBER_ROLE,
                needs_legal_acceptance=False,
            ),
            cookie=await self._open_auth(session, user_id, user_agent, now),
        )

    async def _reissue_standalone(self, user_id: UUID, user_agent: str) -> Completion:
        """`_reissue` numa transação própria, para o formulário de uma sessão concluída."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            return await self._reissue(session, user_id, user_agent, self._clock.now())
        # Nunca roda; só satisfaz o mypy, como em `_accept_locked`.
        raise RuntimeError("registration session")

    async def _reissue(
        self,
        session: AsyncSession,
        user_id: UUID,
        user_agent: str,
        now: datetime,
    ) -> Completion:
        """Resposta idempotente de uma conclusão repetida: o mesmo usuário, um cookie novo.

        Abre outra sessão de autenticação sem pedir senha. Quem tem o id de uma sessão de
        cadastro concluída consegue isso até o `retention-job` apagar a linha, depois do
        `expires_at` de 24 horas. Usuário apagado no meio tempo responde 404.
        """
        user = await UserRepository(session).get_by_id(user_id)
        if user is None:
            raise NotFound(NOT_FOUND)
        version = None
        if await ConsentRepository(session).has_current_terms(user_id, LEGAL_DOCUMENT_VERSION):
            version = LEGAL_DOCUMENT_VERSION
        return Completion(
            profile=Profile(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                phone=user.phone,
                visitor_type=user.visitor_type,
                visit_reason=user.visit_reason,
                role=user.role,
                needs_legal_acceptance=needs_legal_acceptance(version),
            ),
            cookie=await self._open_auth(session, user_id, user_agent, now),
        )

    async def _open_auth(
        self,
        session: AsyncSession,
        user_id: UUID,
        user_agent: str,
        now: datetime,
    ) -> SessionCookie:
        """Grava uma sessão de autenticação de 14 dias e devolve o cookie `atrium_session`.

        O cookie leva o segredo de 256 bits; o banco guarda só o SHA-256 dele (seção 8.1).
        Roda na transação de quem chama.
        """
        secret = new_session_secret()
        await AuthSessionRepository(session).create(
            token_hash=hash_session_secret(secret),
            user_id=user_id,
            expires_at=now + timedelta(seconds=SESSION_MAX_AGE_SECONDS),
            user_agent=clean_user_agent(user_agent),
        )
        return session_cookie(secret=secret, app_env=self._app_env)

    async def _open(self, session_id: UUID) -> tuple[RegistrationRecord, Machine]:
        """Lê a sessão numa transação curta, sem trava, e remonta a máquina.

        Inexistente levanta `NotFound` (404). Vencida é marcada `abandoned` dentro da
        transação, que confirma, e só então `ValidationFailed` com `EXPIRED` sobe (422).
        """
        now = self._clock.now()
        error: DomainError | None = None
        record: RegistrationRecord | None = None
        async with open_session(self._database_url) as session, UnitOfWork(session):
            current = await RegistrationRepository(session).get(session_id)
            if current is None:
                error = NotFound(NOT_FOUND)
            else:
                closed = await _close_if_needed(session, current, now)
                if closed is not None:
                    error = closed
                else:
                    record = current
        # O erro sobe depois do commit, com o abandono já gravado.
        if error is not None:
            raise error
        if record is None:
            raise NotFound(NOT_FOUND)
        return record, _machine(record)

    async def _save(
        self,
        record: RegistrationRecord,
        machine: Machine,
        transcript: tuple[TranscriptItem, ...],
        password_hash: str | None,
    ) -> RegistrationRecord:
        """A transação de escrita de cada passo do cadastro.

        Trava a linha (`SELECT ... FOR UPDATE`), fecha a sessão se ela venceu (422) e recusa
        com 422 quando o `status` mudou desde a leitura em `_open`, como num passo feito em
        outra aba. Grava status, documento de campos, hash e transcrição. Só o status é
        comparado (Etapa 13.3).
        """
        now = self._clock.now()
        error: DomainError | None = None
        saved: RegistrationRecord | None = None
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repo = RegistrationRepository(session)
            current = await repo.lock(record.id)
            if current is None:
                error = NotFound(NOT_FOUND)
            else:
                closed = await _close_if_needed(session, current, now)
                if closed is not None:
                    error = closed
                elif current.status != record.status:
                    error = ValidationFailed(WRONG_STEP)
                else:
                    saved = await repo.save(
                        replace(
                            current,
                            status=machine.status.value,
                            fields=fields_document(machine),
                            password_hash=password_hash,
                            transcript=dump_transcript(transcript),
                        )
                    )
        if error is not None:
            raise error
        if saved is None:
            raise NotFound(NOT_FOUND)
        return saved

    async def _edit(self, machine: Machine, edits: dict[str, str | None]) -> Machine:
        """Aplica as edições do cartão, com a regra do e-mail já usado.

        Um e-mail válido que já tem conta sai das edições e vira o erro de campo `taken`,
        sem sobrescrever o e-mail guardado (seção 7.2). O resto vai para `apply_edits`, no
        domínio. A conferência do e-mail é uma leitura curta própria.
        """
        remaining = dict(edits)
        taken = False
        raw_email = remaining.get("email")
        if isinstance(raw_email, str) and raw_email.strip():
            normalized, issue = validate_field("email", raw_email)
            if issue is None and normalized is not None and await self._email_taken(normalized):
                taken = True
                remaining.pop("email")
        updated = apply_edits(machine, remaining)
        if taken:
            return with_issue(updated, FieldIssue("email", "taken"))
        return updated

    async def _limit(self, client_ip: str) -> None:
        """Balde de 20 por hora por IP das mensagens, da senha e do formulário (seção 10.4).

        Transação própria, que confirma o contador mesmo quando o pedido é recusado. A chave
        é o HMAC do IP com o sal do dia. Erros: `RateLimited` (429), e `RuntimeError` sem
        `RATE_LIMIT_HMAC_KEY`.
        """
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")
        now = self._clock.now()
        window = registration_window_start(now)
        key = bucket_key(
            purpose=REGISTRATION_IP_PURPOSE,
            subject=client_ip,
            day=now.astimezone(UTC).date(),
            key=self._hmac_key,
        )
        async with open_session(self._database_url) as session, UnitOfWork(session):
            count = await RateLimitRepository(session).increment(key, window)
            decision = registration_rate_decision(count=count, now=now, window_start=window)
        if decision.limited:
            raise RateLimited(RATE_LIMITED, retry_after_seconds=decision.retry_after_seconds)

    async def _email_taken(self, email: str) -> bool:
        """Diz se o e-mail já tem conta, numa leitura curta própria.

        Vai como callback ao workflow, que o chama entre as duas chamadas ao modelo.
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            return await UserRepository(session).get_by_email(email) is not None
        # Nunca roda; só satisfaz o mypy, como em `_accept_locked`.
        raise RuntimeError("registration session")


def _draft_from_form(form: FormInput) -> MemberDraft:
    """Valida o formulário com as regras dos campos, da senha e dos aceites.

    Junta todos os erros num só `ValidationFailed` (422) com `field_errors`. Sem a
    personalização, o rascunho já vem sem `visitor_type` e `visit_reason`.
    """
    fields, issues = collect_form(
        FormValues(
            full_name=form.full_name,
            email=form.email,
            phone=form.phone,
            visitor_type=form.visitor_type,
            visit_reason=form.visit_reason,
        )
    )
    if not password_is_acceptable(form.password):
        issues = (*issues, FieldIssue("password", "invalid"))
    if issues:
        raise ValidationFailed(COMPLETION_FAILED, field_errors=_messages(issues))
    draft = draft_member(
        fields,
        Acceptance(
            accept_terms=form.accept_terms,
            document_version=form.document_version,
            age_18_plus=form.age_18_plus,
            profile_personalization=form.profile_personalization,
            quality_improvement=form.quality_improvement,
        ),
        expected_version=LEGAL_DOCUMENT_VERSION,
        password_ready=True,
    )
    if not isinstance(draft, MemberDraft):
        raise ValidationFailed(COMPLETION_FAILED, field_errors=_messages(draft))
    return draft


def _view(record: RegistrationRecord, machine: Machine, prompt: str) -> SessionView:
    """Monta a resposta da sessão. Os erros de campo viram mensagens em português."""
    return SessionView(
        id=record.id,
        status=machine.status.value,
        path=_path(record.path),
        fields=public_fields(machine.fields),
        field_errors=_messages(machine.field_errors),
        next_step=machine.next_step.value,
        prompt=prompt,
        messages=load_transcript(record.transcript),
        expires_at=record.expires_at,
    )


def _step_prompt(machine: Machine) -> str:
    """A fala fixa do próximo passo, sem o Gemini.

    Na revisão, fora do modo de correção, é o resumo dos campos com os rótulos em
    português e a pergunta final (seção 7.2).
    """
    if machine.next_step == Step.REVIEW and not machine.correcting:
        return review_prompt(asdict(public_fields(machine.fields)))
    return prompt_for(machine.next_step.value, correcting=machine.correcting)


def _stored_prompt(record: RegistrationRecord, machine: Machine) -> str:
    """A última fala do assistente na transcrição, ou a fala fixa do passo se não há."""
    for item in reversed(load_transcript(record.transcript)):
        if item.role == "assistant":
            return item.text
    return prompt_for(machine.next_step.value, correcting=machine.correcting)


def _messages(issues: tuple[FieldIssue, ...]) -> dict[str, str]:
    """Erros de campo do domínio para `field_errors`: campo e mensagem em português."""
    return {issue.field: message_for(issue.field, issue.code) for issue in issues}


def _machine(record: RegistrationRecord) -> Machine:
    """Remonta a máquina do documento JSON. A senha conta como definida pela coluna do hash."""
    return machine_from_document(
        record.status,
        record.fields,
        password_set=record.password_hash is not None,
    )


def _completed(record: RegistrationRecord, draft: MemberDraft, user_id: UUID) -> RegistrationRecord:
    """A sessão concluída: campos finais, sem transcrição, sem hash e com o usuário.

    Conta `completed` com o caminho da sessão. O contador sobe aqui, dentro da transação,
    então uma confirmação que falhe depois já foi contada.
    """
    REGISTRATION_EVENTS.labels(event="completed", path=record.path).inc()
    return replace(
        record,
        status=Status.COMPLETED.value,
        fields=completed_document(draft),
        password_hash=None,
        transcript=[],
        user_id=user_id,
    )


def _abandoned(record: RegistrationRecord) -> RegistrationRecord:
    """A sessão abandonada, sem hash nem transcrição (seção 8.1). Conta `abandoned`.

    Só acontece quando alguém toca de novo numa sessão vencida. Uma sessão que só expira
    sai pelo `retention-job`, sem passar por aqui e sem métrica.
    """
    REGISTRATION_EVENTS.labels(event="abandoned", path=record.path).inc()
    return replace(record, status=Status.ABANDONED.value, password_hash=None, transcript=[])


async def _close_if_needed(
    session: AsyncSession,
    record: RegistrationRecord,
    now: datetime,
) -> DomainError | None:
    """Erro `EXPIRED` (422) para uma sessão abandonada ou vencida, ou `None` se ela vale.

    Uma sessão vencida e ainda aberta é gravada como `abandoned` na transação de quem
    chama. Uma sessão concluída nunca vence aqui, então o aceite repetido continua
    funcionando até a retenção apagar a linha.
    """
    if record.status == Status.ABANDONED.value:
        return ValidationFailed(EXPIRED)
    if not session_is_expired(status=record.status, expires_at=record.expires_at, now=now):
        return None
    await RegistrationRepository(session).save(_abandoned(record))
    return ValidationFailed(EXPIRED)


def _path(value: str) -> PathName:
    """O caminho gravado como literal. Outro valor seria um banco fora do `CHECK`."""
    if value == Path.FORM.value:
        return "form"
    if value == Path.CHAT.value:
        return "chat"
    raise RuntimeError("registration path")


async def _guest_id(session: AsyncSession, secret: str | None) -> UUID | None:
    """A chave de convidado do cookie `atrium_guest`, achada pelo SHA-256 do segredo."""
    if not secret:
        return None
    found = await ConversationRepository(session).get_guest_key_by_hash(hash_session_secret(secret))
    if found is None:
        return None
    return found.id
