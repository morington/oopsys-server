from types import SimpleNamespace

from oopsys_server.application.projects import rule_matches, slugify


def _rule(match_type: str, match_value: str) -> SimpleNamespace:
    return SimpleNamespace(match_type=match_type, match_value=match_value)


def test_slugify():
    assert slugify("Crypto Bot 1") == "crypto-bot-1"
    assert slugify("  ---  ") == "project"


def test_rule_matches_service_direct():
    assert rule_matches(_rule("service", "bot"), service="bot", name="x", labels={}) is True


def test_rule_matches_service_via_compose_label():
    labels = {"com.docker.compose.service": "bot"}
    assert rule_matches(_rule("service", "bot"), service="", name="x", labels=labels) is True


def test_rule_matches_container_name():
    assert rule_matches(_rule("container_name", "web"), service="", name="web", labels={}) is True
    assert rule_matches(_rule("container_name", "web"), service="", name="db", labels={}) is False


def test_rule_matches_label_key_value():
    labels = {"com.docker.compose.project": "cryptobot"}
    rule = _rule("label", "com.docker.compose.project=cryptobot")
    assert rule_matches(rule, service="", name="x", labels=labels) is True


def test_rule_matches_label_key_only():
    assert rule_matches(_rule("label", "tier"), service="", name="x", labels={"tier": "web"}) is True
