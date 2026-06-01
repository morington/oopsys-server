from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import VerifyMismatchError


class PasswordHasher:

    def __init__(self) -> None:
        self._hasher = _Argon2()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, hashed: str, password: str) -> bool:
        try:
            self._hasher.verify(hashed, password)
        except (VerifyMismatchError, Exception):
            return False
        return True

    def needs_rehash(self, hashed: str) -> bool:
        return self._hasher.check_needs_rehash(hashed)
