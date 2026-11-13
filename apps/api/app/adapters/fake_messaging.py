"""Adaptador falso da porta `MessagingChannel`, para os testes. NFR-24 do SDD.

Camada de adaptadores. Grava cada envio em `sent` e cada confirmação de leitura em `read`, e
devolve `wamid` sequenciais. `fail_with` faz os próximos envios levantarem `SendError`, para
os testes das novas tentativas. Nenhuma chamada sai da máquina.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.domain.whatsapp import Recipient
from app.ports.messaging import SendButton, SendError


@dataclass(frozen=True, slots=True)
class SentMessage:
    """Um envio gravado: destino, texto, botões e o `wamid` devolvido."""

    recipient: Recipient
    text: str
    buttons: tuple[SendButton, ...]
    wamid: str


@dataclass
class FakeMessagingChannel:
    """Guarda o que seria enviado à Meta."""

    sent: list[SentMessage] = field(default_factory=list)
    read: list[str] = field(default_factory=list)
    failures: list[SendError] = field(default_factory=list)

    def fail_with(self, *errors: SendError) -> None:
        """Os próximos envios levantam estes erros, um por envio, na ordem."""
        self.failures.extend(errors)

    async def send_text(self, recipient: Recipient, text: str) -> str:
        return self._record(recipient, text, ())

    async def send_buttons(
        self, recipient: Recipient, text: str, buttons: Sequence[SendButton]
    ) -> str:
        return self._record(recipient, text, tuple(buttons))

    async def mark_read_typing(self, wamid: str) -> None:
        self.read.append(wamid)

    def _record(self, recipient: Recipient, text: str, buttons: tuple[SendButton, ...]) -> str:
        if self.failures:
            raise self.failures.pop(0)
        wamid = f"wamid.fake.{len(self.sent) + 1}"
        self.sent.append(SentMessage(recipient=recipient, text=text, buttons=buttons, wamid=wamid))
        return wamid
