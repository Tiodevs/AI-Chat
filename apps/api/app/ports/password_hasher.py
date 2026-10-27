from typing import Protocol


class PasswordHasher(Protocol):
    def hash_password(self, password: str) -> str: ...

    def verify_password(self, password: str, password_hash: str) -> bool: ...

    @property
    def dummy_hash(self) -> str: ...
