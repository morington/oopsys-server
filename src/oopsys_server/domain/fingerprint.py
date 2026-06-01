import hashlib
import re

_HEX = re.compile("\\b0x[0-9a-fA-F]+\\b")
_UUID = re.compile("\\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\\b")
_NUMBER = re.compile("\\b\\d+\\b")
_PATH = re.compile("(/[^\\s'\\\"]+)+")
_QUOTED = re.compile("(['\\\"]).*?\\1")
_WS = re.compile("\\s+")


def normalize_message(message: str) -> str:
    text = message.strip()
    text = _UUID.sub("<uuid>", text)
    text = _HEX.sub("<hex>", text)
    text = _PATH.sub("<path>", text)
    text = _QUOTED.sub("<str>", text)
    text = _NUMBER.sub("<n>", text)
    return _WS.sub(" ", text).strip().lower()


def _top_frame(traceback: str) -> str:
    frames = [line.strip() for line in traceback.splitlines() if line.strip().startswith("File ")]
    if not frames:
        return ""
    last = frames[-1]
    return re.sub("line \\d+", "line <n>", last)


def compute_fingerprint(*, service: str, exception_type: str, message: str, traceback: str = "") -> str:
    parts = [service, exception_type, normalize_message(message), _top_frame(traceback)]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
