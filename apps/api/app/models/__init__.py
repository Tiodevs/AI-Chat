"""Entidades SQLAlchemy. Sem tratador de pedido. Seção 6.2 do SDD."""

from app.models.audit_event import AuditEvent
from app.models.auth_session import AuthSession
from app.models.base import Base
from app.models.chunk import Chunk
from app.models.consent_record import ConsentRecord
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.feedback import Feedback
from app.models.guest_key import GuestKey
from app.models.message import Message
from app.models.rate_limit_window import RateLimitWindow
from app.models.registration_session import RegistrationSession
from app.models.token_usage_day import TokenUsageDay
from app.models.user import User

__all__ = [
    "AuditEvent",
    "AuthSession",
    "Base",
    "Chunk",
    "ConsentRecord",
    "Conversation",
    "Document",
    "DocumentVersion",
    "Feedback",
    "GuestKey",
    "Message",
    "RateLimitWindow",
    "RegistrationSession",
    "TokenUsageDay",
    "User",
]
