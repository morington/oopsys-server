import httpx


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
