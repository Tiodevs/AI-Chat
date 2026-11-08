"""Escolhe o adaptador de chat. Seção 17 do SDD.

Padrão Strategy da seção 6.2: a configuração escolhe a implementação da porta de chat num
lugar só, sem `if` espalhado pelo código. Quem usa: `build_ai_runtime` em
`app.core.container`, uma vez por processo, e os scripts `ask` e `run_evals`.

| `APP_AI_ADAPTER` | Chave do Gemini | Provedor |
|---|---|---|
| `fake` | qualquer | `FakeChatProvider` sem roteiro: toda chamada falha como indisponível |
| `demo` | qualquer | `DemoChatProvider`, por regras e sem rede (ADR-014) |
| `gemini` | vazia | `UnavailableChatProvider` |
| `gemini` | preenchida | `GeminiChatProvider` com `CHAT_MODEL` |
"""

from app.adapters.demo_chat import DemoChatProvider
from app.adapters.fake_chat import FakeChatProvider
from app.adapters.gemini_chat import GeminiChatProvider
from app.adapters.unavailable import UnavailableChatProvider
from app.core.config import Settings
from app.ports.chat import ChatProvider


def build_chat_provider(settings: Settings) -> ChatProvider:
    """O provedor de chat da configuração, pela tabela do cabeçalho deste arquivo.

    A configuração recusa `demo` em `development` e `production` (`app.core.config`). O
    `fake` não é recusado lá; quem fixa `gemini` nesses ambientes é a seção 19.
    """
    if settings.app_ai_adapter == "fake":
        return FakeChatProvider()
    if settings.app_ai_adapter == "demo":
        return DemoChatProvider()
    if not settings.gemini_api_key:
        # Sem chave, degrada na chamada em vez de falhar ao montar o workflow (SDD 22.1).
        return UnavailableChatProvider(settings.chat_model)
    return GeminiChatProvider(api_key=settings.gemini_api_key, model=settings.chat_model)
