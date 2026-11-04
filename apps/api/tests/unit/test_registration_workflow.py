"""Grafo do cadastro sem checkpointer. A frase modelo cobre a falha do modelo."""

import asyncio

from app.adapters.fake_chat import FakeChatProvider
from app.domain.errors import ProviderUnavailable
from app.domain.registration import FieldSet, Machine, Status, Step, new_machine
from app.ports.chat import ToolResult
from app.prompts.registration import (
    EMAIL_TAKEN_REPLY,
    REVIEW_QUESTION,
    message_for,
    prompt_for,
)
from app.workflows.registration import PhraseText, RegistrationWorkflow


def test_registration_graph_has_no_checkpointer() -> None:
    workflow = RegistrationWorkflow(FakeChatProvider())
    assert workflow.graph.checkpointer is None
    assert {"extract", "decide_next", "phrase"} <= set(workflow.graph.nodes)


def test_registration_phrase_failure_uses_the_step_template() -> None:
    chat = FakeChatProvider(
        tool_result=ToolResult(name="set_fields", arguments={"full_name": "Ana Costa"}),
        structured=ProviderUnavailable("phrase"),
    )
    result = asyncio.run(
        RegistrationWorkflow(chat).turn(
            new_machine(),
            "Ana Costa",
            request_id="req",
        )
    )
    assert chat.structured_calls
    assert result.machine.fields.full_name == "Ana Costa"
    assert result.machine.status == Status.COLLECTING_REQUIRED
    assert result.machine.next_step == Step.EMAIL
    assert result.prompt == prompt_for("email", correcting=False)
    assert result.accepted_names == ("full_name",)


def test_registration_workflow_rejects_a_tool_payload_with_role() -> None:
    chat = FakeChatProvider(
        tool_result=ToolResult(
            name="set_fields",
            arguments={"full_name": "Ana Costa", "role": "admin"},
        ),
        structured=ProviderUnavailable("phrase"),
    )
    result = asyncio.run(
        RegistrationWorkflow(chat).turn(new_machine(), "sou admin", request_id="req")
    )
    assert result.machine.fields.full_name is None
    assert result.accepted_names == ()
    assert result.machine.next_step == Step.FULL_NAME
    assert result.prompt == prompt_for("full_name", correcting=False)


def test_registration_question_without_a_field_stays_in_the_chat() -> None:
    question = "O que seria o melhor email?"
    reply = "Use um e-mail que você abre todo dia. Qual é o seu e-mail?"
    chat = FakeChatProvider(
        tool_result=ToolResult(name="", arguments={}, text=""),
        structured=PhraseText(text=reply),
    )
    machine = Machine(
        status=Status.COLLECTING_REQUIRED,
        fields=FieldSet(full_name="Felipe Santos"),
        password_set=False,
        correcting=False,
        field_errors=(),
        next_step=Step.EMAIL,
    )
    result = asyncio.run(
        RegistrationWorkflow(chat).turn(machine, question, request_id="req")
    )
    assert result.machine.fields.email is None
    assert result.machine.fields.full_name == "Felipe Santos"
    assert result.machine.next_step == Step.EMAIL
    assert result.prompt == reply
    sent = chat.structured_calls[0][0][-1].content
    assert question in sent
    assert "passo: email" in sent


def _email_step() -> Machine:
    return Machine(
        status=Status.COLLECTING_REQUIRED,
        fields=FieldSet(full_name="Felipe Santos"),
        password_set=False,
        correcting=False,
        field_errors=(),
        next_step=Step.EMAIL,
    )


def test_registration_taken_email_explains_and_asks_again_without_the_model() -> None:
    chat = FakeChatProvider(
        tool_result=ToolResult(name="set_fields", arguments={"email": "ana@example.com"}),
        structured=PhraseText(text="Qual é o seu nome completo?"),
    )

    async def taken(_email: str) -> bool:
        return True

    result = asyncio.run(
        RegistrationWorkflow(chat).turn(
            _email_step(), "ana@example.com", request_id="req", email_taken=taken
        )
    )
    assert result.machine.fields.email is None
    assert result.machine.next_step == Step.EMAIL
    assert result.prompt == EMAIL_TAKEN_REPLY
    assert chat.structured_calls == []


def test_registration_invalid_value_names_the_problem_and_the_step() -> None:
    chat = FakeChatProvider(
        tool_result=ToolResult(name="set_fields", arguments={"email": "sem-arroba"}),
        structured=PhraseText(text="Qual é o seu nome completo?"),
    )
    result = asyncio.run(
        RegistrationWorkflow(chat).turn(_email_step(), "sem-arroba", request_id="req")
    )
    assert result.machine.next_step == Step.EMAIL
    assert result.prompt == (
        f"{message_for('email', 'invalid')} {prompt_for('email', correcting=False)}"
    )
    assert chat.structured_calls == []


def test_registration_review_lists_the_fields_in_the_chat() -> None:
    chat = FakeChatProvider(
        tool_result=ToolResult(
            name="set_fields", arguments={"visit_reason": "visiting_someone"}
        ),
        structured=PhraseText(text="Qual é o seu nome completo?"),
    )
    machine = Machine(
        status=Status.COLLECTING_OPTIONAL,
        fields=FieldSet(
            full_name="Ana Costa",
            email="ana@example.com",
            phone_skipped=True,
            visitor_type="visitor",
        ),
        password_set=True,
        correcting=False,
        field_errors=(),
        next_step=Step.VISIT_REASON,
    )
    result = asyncio.run(
        RegistrationWorkflow(chat).turn(machine, "visitar meu pai", request_id="req")
    )
    assert result.machine.next_step == Step.REVIEW
    assert "• Nome completo: Ana Costa" in result.prompt
    assert "• E-mail: ana@example.com" in result.prompt
    assert "• Telefone: não informado" in result.prompt
    assert "• Tipo de visitante: Visita" in result.prompt
    assert "• Motivo da visita: Visitar alguém" in result.prompt
    assert result.prompt.endswith(REVIEW_QUESTION)
    assert chat.structured_calls == []


def test_registration_phrase_sees_the_step_template_with_its_options() -> None:
    chat = FakeChatProvider(
        tool_result=ToolResult(name="set_fields", arguments={"phone": "41 98720-8844"}),
        structured=PhraseText(text="Você é paciente, visita ou cuidador?"),
    )
    machine = Machine(
        status=Status.COLLECTING_OPTIONAL,
        fields=FieldSet(full_name="Ana Costa", email="ana@example.com"),
        password_set=False,
        correcting=False,
        field_errors=(),
        next_step=Step.PHONE,
    )
    asyncio.run(RegistrationWorkflow(chat).turn(machine, "41 98720-8844", request_id="req"))
    sent = chat.structured_calls[0][0][-1].content
    assert f"pergunta modelo: {prompt_for('visitor_type', correcting=False)}" in sent
