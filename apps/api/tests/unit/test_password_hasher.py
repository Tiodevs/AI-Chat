from app.adapters.password_hasher import Argon2idPasswordHasher


def test_password_is_stored_as_argon2id() -> None:
    hasher = Argon2idPasswordHasher()
    password = "correct-horse-1"
    stored = hasher.hash_password(password)
    assert stored.startswith("$argon2id$")
    assert password not in stored
    assert hasher.verify_password(password, stored)
    assert not hasher.verify_password("wrong-password-1", stored)
    assert not hasher.verify_password(password, "not-a-hash")
