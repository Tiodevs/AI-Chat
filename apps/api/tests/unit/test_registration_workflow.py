"""Grafo do cadastro sem checkpointer. A frase modelo cobre a falha do modelo."""

import asyncio

from app.adapters.fake_chat import FakeChatProvider
from app.domain.errors import ProviderUnavailable
from app.domain.registration import Status, Step, new_machine
from app.ports.chat import ToolResult
from app.prompts.registration import prompt_for
from app.workflows.registration import RegistrationWorkflow


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
