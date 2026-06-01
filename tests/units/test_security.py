from oopsys_server.infrastructure.security import PasswordHasher, TokenCipher, generate_token, hash_token
from oopsys_server.infrastructure.security.captcha import generate_captcha, verify_captcha


def test_password_hash_and_verify():
    hasher = PasswordHasher()
    hashed = hasher.hash("correct horse battery staple")
    assert hasher.verify(hashed, "correct horse battery staple") is True
    assert hasher.verify(hashed, "wrong") is False


def test_token_hash_is_stable_sha256():
    token = "abc"
    assert hash_token(token) == hash_token(token)
    assert len(hash_token(token)) == 64


def test_generate_token_is_unique():
    assert generate_token() != generate_token()


def test_token_cipher_round_trip():
    cipher = TokenCipher("super-secret")
    encrypted = cipher.encrypt("123:secret-bot-token")
    assert encrypted != "123:secret-bot-token"
    assert cipher.decrypt(encrypted) == "123:secret-bot-token"


def test_token_cipher_wrong_key_returns_none():
    encrypted = TokenCipher("key-a").encrypt("value")
    assert TokenCipher("key-b").decrypt(encrypted) is None


def test_captcha_verifies_only_correct_answer():
    challenge = generate_captcha()
    assert challenge.data_uri.startswith("data:image/png;base64,")
    assert verify_captcha(challenge.answer_hash, "definitely-wrong") is False
