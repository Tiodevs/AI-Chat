"""Escolhe o adaptador de chat. Seção 17 do SDD."""

from app.adapters.fake_chat import FakeChatProvider
from app.adapters.gemini_chat import GeminiChatProvider
from app.core.config import Settings
from app.ports.chat import ChatProvider


def build_chat_provider(settings: Settings) -> ChatProvider:
    if settings.app_ai_adapter == "fake":
        return FakeChatProvider()
    return GeminiChatProvider(api_key=settings.gemini_api_key, model=settings.chat_model)
