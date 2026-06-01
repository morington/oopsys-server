import secrets

from itsdangerous import BadSignature, URLSafeSerializer

CSRF_COOKIE = "oopsys_csrf"
CSRF_FIELD = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"

class CsrfProtection:

    def __init__(self, secret_key: str) -> None:
        self._serializer = URLSafeSerializer(secret_key, salt="oopsys-csrf")

    def issue(self) -> tuple[str, str]:
        raw = secrets.token_urlsafe(32)
        return (self._serializer.dumps(raw), raw)

    def unsign(self, cookie_value: str | None) -> str | None:
        if not cookie_value:
            return None
        try:
            return self._serializer.loads(cookie_value)
        except BadSignature:
            return None

    def validate(self, cookie_value: str | None, submitted: str | None) -> bool:
        expected = self.unsign(cookie_value)
        return bool(expected) and bool(submitted) and secrets.compare_digest(expected, submitted)
