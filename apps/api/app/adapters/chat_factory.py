"""Escolhe o adaptador de chat. Seção 17 do SDD."""

from app.adapters.demo_chat import DemoChatProvider
from app.adapters.fake_chat import FakeChatProvider
from app.adapters.gemini_chat import GeminiChatProvider
from app.adapters.unavailable import UnavailableChatProvider
from app.core.config import Settings
from app.ports.chat import ChatProvider


def build_chat_provider(settings: Settings) -> ChatProvider:
    if settings.app_ai_adapter == "fake":
        return FakeChatProvider()
    if settings.app_ai_adapter == "demo":
        return DemoChatProvider()
    if not settings.gemini_api_key:
        # Sem chave, degrada na chamada em vez de falhar ao montar o workflow (SDD 22.1).
        return UnavailableChatProvider(settings.chat_model)
    return GeminiChatProvider(api_key=settings.gemini_api_key, model=settings.chat_model)
