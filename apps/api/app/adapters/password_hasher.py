"""argon2id. A senha nunca volta na resposta. Seção 8.5 do SDD.

Implementa a porta `PasswordHasher` (`app.ports.password_hasher`) com a biblioteca
`argon2-cffi`, nos parâmetros padrão dela. Quem usa: `get_password_hasher`, chamado pelos
controladores de conta, autenticação, admin e privacidade, pelo `app.core.container` (cadastro)
e pelo script `bootstrap_admin`.

As chamadas são síncronas e gastam CPU de propósito. Hoje rodam direto no loop de eventos do
login e do cadastro; a Etapa 13.1 as leva para `asyncio.to_thread`.
"""

from argon2 import PasswordHasher
from argon2 import Type as Argon2Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class Argon2idPasswordHasher:
    """Hash e verificação de senha com argon2id, mais um hash de mentira para o login.

    O construtor calcula `dummy_hash` uma vez. O `AuthService` verifica a senha contra ele
    quando o e-mail não existe, para o login gastar o mesmo tempo e não revelar se a conta
    existe (seção 10.4).
    """

    def __init__(self) -> None:
        self._hasher = PasswordHasher(type=Argon2Type.ID)
        self._dummy = self._hasher.hash("atrium-dummy-password")

    def hash_password(self, password: str) -> str:
        """O hash argon2id da senha, com sal novo a cada chamada, no formato PHC."""
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Diz se a senha confere com o hash. Hash inválido ou senha errada devolvem `False`."""
        try:
            self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
        return True

    @property
    def dummy_hash(self) -> str:
        """O hash de uma senha fixa de mentira, só para gastar o tempo de uma verificação."""
        return self._dummy


_hasher: Argon2idPasswordHasher | None = None


def get_password_hasher() -> Argon2idPasswordHasher:
    """O hasher do processo, criado no primeiro uso, porque o construtor já calcula um hash."""
    global _hasher
    if _hasher is None:
        _hasher = Argon2idPasswordHasher()
    return _hasher
