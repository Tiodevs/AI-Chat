import pytest

from tests.architecture.layers import import_violations, package_violations


def test_packages_respect_section_6_2() -> None:
    assert package_violations() == []


def test_controller_importing_sqlalchemy_is_reported() -> None:
    violations = import_violations("app.controllers.health", "import sqlalchemy\n")
    assert violations == ["app.controllers.health imports sqlalchemy"]


@pytest.mark.parametrize(
    ("module", "source"),
    [
        ("app.domain.rules", "import fastapi\n"),
        ("app.domain.rules", "from app.core.config import Settings\n"),
        ("app.controllers.health", "from sqlalchemy.orm import Session\n"),
        ("app.controllers.health", "import langchain\n"),
        ("app.controllers.health", "import langgraph\n"),
        ("app.controllers.health", "import langsmith\n"),
        (
            "app.controllers.health",
            "from app.repositories.readiness import ReadinessRepository\n",
        ),
        (
            "app.controllers.health",
            "from ..repositories.readiness import ReadinessRepository\n",
        ),
        ("app.services.readiness", "import fastapi\n"),
        ("app.services.readiness", "import langchain\n"),
        ("app.services.readiness", "import langgraph\n"),
        ("app.services.readiness", "import langsmith\n"),
        ("app.workflows.qa", "import fastapi\n"),
        ("app.workflows.qa", "import sqlalchemy\n"),
        ("app.repositories.readiness", "import fastapi\n"),
        ("app.repositories.readiness", "import langchain\n"),
        ("app.repositories.readiness", "import langgraph\n"),
        ("app.repositories.readiness", "import langsmith\n"),
        ("app.models.user", "import fastapi\n"),
        ("app.models.user", "import langchain\n"),
    ],
)
def test_forbidden_import_is_reported(module: str, source: str) -> None:
    assert import_violations(module, source)


def test_domain_can_import_the_standard_library_and_pydantic() -> None:
    source = (
        "import json\n"
        "from pydantic import BaseModel\n"
        "from app.domain.errors import DomainError\n"
    )
    assert import_violations("app.domain.rules", source) == []


def test_service_can_import_a_repository() -> None:
    source = "from app.repositories.readiness import ReadinessRepository\n"
    assert import_violations("app.services.readiness", source) == []
