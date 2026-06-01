import base64
import io
import random
import secrets
import string
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from oopsys_server.infrastructure.security.tokens import hash_token

_ALPHABET = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"

@dataclass(slots=True)
class CaptchaChallenge:
    answer_hash: str
    data_uri: str

def _load_font(size: int) -> ImageFont.ImageFont:
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)

def generate_captcha(length: int=5) -> CaptchaChallenge:
    text = "".join(secrets.choice(_ALPHABET) for _ in range(length))
    width, height = (200, 70)
    image = Image.new("RGB", (width, height), (245, 246, 248))
    draw = ImageDraw.Draw(image)
    font = _load_font(40)
    for _ in range(6):
        start = (random.randint(0, width), random.randint(0, height))
        end = (random.randint(0, width), random.randint(0, height))
        draw.line([start, end], fill=(210, 212, 216), width=2)
    x = 18
    for char in text:
        y = random.randint(8, 24)
        draw.text((x, y), char, font=font, fill=(60, 64, 72))
        x += 34
    for _ in range(450):
        xy = (random.randint(0, width), random.randint(0, height))
        draw.point(xy, fill=(190, 192, 196))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return CaptchaChallenge(answer_hash=hash_token(text.upper()), data_uri=f"data:image/png;base64,{encoded}")

def verify_captcha(answer_hash: str, attempt: str) -> bool:
    return bool(attempt) and hash_token(attempt.strip().upper()) == answer_hash
