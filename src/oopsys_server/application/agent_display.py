"""Human-readable names for agents in UI and notifications."""


def resolve_agent_display_name(
    *,
    token_label: str | None = None,
    agent_name: str | None = None,
    agent_id: str,
) -> str:
    """Prefer account token label, then agent-reported name, then short id."""
    for value in (token_label, agent_name):
        if value and value.strip():
            return value.strip()
    return agent_id[:8] if len(agent_id) >= 8 else agent_id
