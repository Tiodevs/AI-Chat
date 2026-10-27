"""argon2id. A senha nunca volta na resposta. Seção 8.5 do SDD."""

from argon2 import PasswordHasher
from argon2 import Type as Argon2Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class Argon2idPasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHasher(type=Argon2Type.ID)
        self._dummy = self._hasher.hash("atrium-dummy-password")

    def hash_password(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
        return True

    @property
    def dummy_hash(self) -> str:
        return self._dummy


_hasher: Argon2idPasswordHasher | None = None


def get_password_hasher() -> Argon2idPasswordHasher:
    global _hasher
    if _hasher is None:
        _hasher = Argon2idPasswordHasher()
    return _hasher
