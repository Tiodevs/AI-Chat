"""Porta do hash de senha. Seções 8.5 e 11.8 do SDD.

Camada de portas. `AuthService` confere a senha no login, `BootstrapAdminService` cria o hash
do admin e `RegistrationService` cria o hash no cadastro. O adaptador é
`Argon2idPasswordHasher` (`app/adapters/password_hasher.py`), com argon2id. A senha nunca é
gravada nem devolvida: só o hash. Os métodos são síncronos e hoje rodam no loop de eventos; a
Etapa 13.1 do plano passa a chamá-los com `asyncio.to_thread`.
"""

from typing import Protocol


class PasswordHasher(Protocol):
    """Cria e confere hashes de senha."""

    def hash_password(self, password: str) -> str:
        """Hash da senha, com sal aleatório, pronto para gravar."""
        ...

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Diz se a senha corresponde ao hash. Senha errada ou hash inválido devolvem falso."""
        ...

    @property
    def dummy_hash(self) -> str:
        """Hash de uma senha qualquer, calculado uma vez.

        O login confere a senha contra ele quando o e-mail não existe. Assim os dois casos
        passam pelo argon2 e levam tempo parecido, e o erro não revela se o e-mail tem conta
        (seção 10.4).
        """
        ...
