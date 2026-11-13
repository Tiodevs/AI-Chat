"""Porta do envio pelo WhatsApp. Seção 30.10 e ADR-017 do SDD.

Camada de portas. O processador do canal (`services/whatsapp.py`) envia texto, botões e a
confirmação de leitura por esta porta. Os adaptadores são o `MetaCloudApiChannel`
(`adapters/whatsapp_cloud.py`), que chama a Graph API da Meta, e o `FakeMessagingChannel`
(`adapters/fake_messaging.py`), que só grava o que seria enviado. Nenhum teste automático
chama a Meta (NFR-24).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.whatsapp import Recipient


@dataclass(frozen=True, slots=True)
class SendButton:
    """Um botão de resposta: o id que volta no webhook e o título visível."""

    id: str
    title: str


class SendError(Exception):
    """A Graph API recusou ou não respondeu. Leva o status HTTP e o código da Meta.

    O texto da exceção nunca tem o corpo da mensagem: só os códigos.
    """

    def __init__(self, *, http_status: int | None, error_code: int | None) -> None:
        super().__init__(f"whatsapp send failed: http={http_status} code={error_code}")
        self.http_status = http_status
        self.error_code = error_code


class MessagingChannel(Protocol):
    """Envio pela Cloud API. Cada método devolve o `wamid` que a Meta deu à mensagem."""

    async def send_text(self, recipient: Recipient, text: str) -> str:
        """Texto livre, sem pré-visualização de link."""
        ...

    async def send_buttons(
        self, recipient: Recipient, text: str, buttons: Sequence[SendButton]
    ) -> str:
        """Mensagem interativa com até 3 botões de resposta."""
        ...

    async def mark_read_typing(self, wamid: str) -> None:
        """Marca a mensagem recebida como lida e mostra o indicador de digitação."""
        ...
