import secrets
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class _Captcha:
    answer_hash: str
    expires_at: float

class CaptchaStore:

    def __init__(self, ttl: float=300.0) -> None:
        self._ttl = ttl
        self._items: dict[str, _Captcha] = {}

    def put(self, answer_hash: str) -> str:
        self._evict()
        captcha_id = secrets.token_urlsafe(12)
        self._items[captcha_id] = _Captcha(answer_hash=answer_hash, expires_at=time.monotonic() + self._ttl)
        return captcha_id

    def take(self, captcha_id: str) -> str | None:
        item = self._items.pop(captcha_id, None)
        if item is None or item.expires_at < time.monotonic():
            return None
        return item.answer_hash

    def _evict(self) -> None:
        now = time.monotonic()
        for key in [k for k, v in self._items.items() if v.expires_at < now]:
            self._items.pop(key, None)

@dataclass
class LoginGuard:
    captcha_after: int
    _attempts: dict[str, int] = field(default_factory=dict)

    def attempts(self, ip: str) -> int:
        return self._attempts.get(ip, 0)

    def needs_captcha(self, ip: str) -> bool:
        return self.attempts(ip) >= self.captcha_after

    def record_failure(self, ip: str) -> None:
        self._attempts[ip] = self._attempts.get(ip, 0) + 1

    def reset(self, ip: str) -> None:
        self._attempts.pop(ip, None)
