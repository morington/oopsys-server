from typing import Any

import httpx


class AgentHealthClient:

    def __init__(self, *, timeout: float=10.0) -> None:
        self._timeout = timeout

    async def health(self, endpoint_url: str, token: str) -> dict[str, Any] | None:
        url = f"{endpoint_url.rstrip('/')}/health"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers={"Authorization": f"Bearer {token}"})
            if response.status_code >= 400:
                return None
            return response.json()
        except Exception:
            return None
