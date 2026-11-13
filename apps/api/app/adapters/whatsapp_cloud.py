"""Adaptador da porta `MessagingChannel` sobre a Graph API da Meta. Seção 30.10 do SDD.

Camada de adaptadores. O `lifespan` de `app/main.py` cria um por processo quando o canal está
ligado e o entrega ao processador (`services/whatsapp.py`). Usa `httpx` com tempo limite de
10 segundos e o token do usuário do sistema em `Authorization: Bearer`.

O envio vai para `POST /{versão}/{phone_number_id}/messages`. Com o BSUID, o destino é o
campo `recipient`; sem ele, o campo `to` com o telefone (ADR-018). Uma resposta fora de 2xx
vira `SendError` com o status HTTP e o código de erro da Meta, sem o corpo da mensagem.
"""

from collections.abc import Sequence
from typing import Any

import httpx

from app.domain.whatsapp import GRAPH_TIMEOUT_SECONDS, Recipient
from app.ports.messaging import SendButton, SendError

_GRAPH_HOST = "https://graph.facebook.com"


class MetaCloudApiChannel:
    """Envia pela Cloud API com o `phone_number_id` do Atrium."""

    def __init__(
        self,
        *,
        access_token: str,
        phone_number_id: str,
        graph_version: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = f"{_GRAPH_HOST}/{graph_version}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {access_token}"}
        self._client = client or httpx.AsyncClient(timeout=GRAPH_TIMEOUT_SECONDS)

    async def send_text(self, recipient: Recipient, text: str) -> str:
        """Texto livre com `preview_url` falso: um link não vira cartão (seção 30.6)."""
        return await self._send(
            recipient, {"type": "text", "text": {"body": text, "preview_url": False}}
        )

    async def send_buttons(
        self, recipient: Recipient, text: str, buttons: Sequence[SendButton]
    ) -> str:
        """Mensagem interativa do tipo `button`, com até 3 botões de resposta."""
        return await self._send(
            recipient,
            {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": text},
                    "action": {
                        "buttons": [
                            {"type": "reply", "reply": {"id": item.id, "title": item.title}}
                            for item in buttons
                        ]
                    },
                },
            },
        )

    async def mark_read_typing(self, wamid: str) -> None:
        """Lida e digitando num pedido só. Nenhum dos dois é cobrado pela Meta."""
        await self._post(
            {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": wamid,
                "typing_indicator": {"type": "text"},
            }
        )

    async def aclose(self) -> None:
        """Fecha o cliente HTTP no desligamento."""
        await self._client.aclose()

    async def _send(self, recipient: Recipient, message: dict[str, Any]) -> str:
        """Monta o destino, envia e devolve o `wamid` da primeira mensagem da resposta."""
        body: dict[str, Any] = {"messaging_product": "whatsapp", "recipient_type": "individual"}
        if recipient.bsuid:
            body["recipient"] = recipient.bsuid
        elif recipient.phone:
            body["to"] = recipient.phone
        else:
            raise SendError(http_status=None, error_code=None)
        body.update(message)
        data = await self._post(body)
        messages = data.get("messages")
        if isinstance(messages, list) and messages and isinstance(messages[0], dict):
            wamid = messages[0].get("id")
            if isinstance(wamid, str) and wamid:
                return wamid
        raise SendError(http_status=200, error_code=None)

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        """Um `POST` à Graph API. Rede fora do ar vira `SendError` sem status."""
        try:
            response = await self._client.post(self._url, json=body, headers=self._headers)
        except httpx.HTTPError:
            raise SendError(http_status=None, error_code=None) from None
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if response.status_code >= 300:
            error = data.get("error")
            code = error.get("code") if isinstance(error, dict) else None
            raise SendError(
                http_status=response.status_code,
                error_code=code if isinstance(code, int) else None,
            )
        return data
