import httpx


class TelegramDeliveryError(Exception):
    """Telegram Bot API rejected sendMessage."""


async def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    """Send a plain-text message to a Telegram chat."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise TelegramDeliveryError(str(exc)) from exc
    if not payload.get("ok"):
        raise TelegramDeliveryError(str(payload.get("description", "unknown error")))


async def fetch_bot_username(token: str) -> str | None:
    """Return Telegram @username for a bot token via getMe."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    if not payload.get("ok"):
        return None
    username = payload.get("result", {}).get("username")
    return str(username) if username else None
