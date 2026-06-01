from oopsys_server.application.agent_display import resolve_agent_display_name
from oopsys_server.infrastructure.persistence.models import Account, Agent
from oopsys_server.infrastructure.persistence.repositories import AgentTokenRepository


async def agent_labels(tokens: AgentTokenRepository, account: Account) -> dict[str, str | None]:
    """Map agent_id to token label for the current account."""
    bound = await tokens.list_for_account(account.id)
    return {token.agent_id: token.label for token in bound if token.agent_id}


def agent_display_name(agent: Agent, labels: dict[str, str | None]) -> str:
    return resolve_agent_display_name(
        token_label=labels.get(agent.agent_id),
        agent_name=agent.name,
        agent_id=agent.agent_id,
    )
