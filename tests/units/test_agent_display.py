from oopsys_server.application.agent_display import resolve_agent_display_name


def test_prefers_token_label() -> None:
    assert (
        resolve_agent_display_name(
            token_label="serverbots",
            agent_name="hostname",
            agent_id="4990da4d-38a9-4f15-a515-8811a6ebf9ec",
        )
        == "serverbots"
    )


def test_falls_back_to_agent_name() -> None:
    assert (
        resolve_agent_display_name(
            agent_name="prod-1",
            agent_id="4990da4d-38a9-4f15-a515-8811a6ebf9ec",
        )
        == "prod-1"
    )


def test_falls_back_to_short_id() -> None:
    assert (
        resolve_agent_display_name(
            agent_id="4990da4d-38a9-4f15-a515-8811a6ebf9ec",
        )
        == "4990da4d"
    )
