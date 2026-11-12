"""Pacote das entidades SQLAlchemy: uma tabela por arquivo, sem tratador de pedido.

Camada de entidade de persistência (seção 6.2 do SDD). Importar o pacote registra todas as
tabelas em `Base.metadata`. É por ele que o `alembic/env.py` e o teste de esquema
(`tests/integration/test_database.py`) enxergam o banco inteiro. Quem lê e grava estas
entidades são os repositórios de `app.repositories`. As tabelas seguem a seção 8.1 do SDD, e o
banco real nasce das migrações em `alembic/versions`.
"""

from app.models.attendant_acknowledgement import AttendantAcknowledgement
from app.models.attendant_presence import AttendantPresence
from app.models.audit_event import AuditEvent
from app.models.auth_session import AuthSession
from app.models.base import Base
from app.models.chunk import Chunk
from app.models.consent_record import ConsentRecord
from app.models.conversation import Conversation
from app.models.data_subject_request import DataSubjectRequest
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.feedback import Feedback
from app.models.guest_key import GuestKey
from app.models.handoff import Handoff
from app.models.message import Message
from app.models.rate_limit_window import RateLimitWindow
from app.models.registration_session import RegistrationSession
from app.models.retention_run import RetentionRun
from app.models.token_usage_day import TokenUsageDay
from app.models.user import User

__all__ = [
    "AttendantAcknowledgement",
    "AttendantPresence",
    "AuditEvent",
    "AuthSession",
    "Base",
    "Chunk",
    "ConsentRecord",
    "Conversation",
    "DataSubjectRequest",
    "Document",
    "DocumentVersion",
    "Feedback",
    "GuestKey",
    "Handoff",
    "Message",
    "RateLimitWindow",
    "RegistrationSession",
    "RetentionRun",
    "TokenUsageDay",
    "User",
]
