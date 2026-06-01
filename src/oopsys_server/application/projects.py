import re
import uuid

from oopsys_server.domain.envelope import ContainerStatePayload
from oopsys_server.infrastructure.persistence.models import ContainerStateRecord, Project, ProjectRule
from oopsys_server.infrastructure.persistence.repositories import ContainerRepository, ProjectRepository

_COMPOSE_PROJECT = "com.docker.compose.project"
_COMPOSE_SERVICE = "com.docker.compose.service"
_SLUG_RE = re.compile("[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "project"


def container_keys(payload: ContainerStatePayload) -> dict[str, str]:
    return {
        "service": payload.labels.get(_COMPOSE_SERVICE, ""),
        "project": payload.labels.get(_COMPOSE_PROJECT, ""),
        "container_name": payload.name,
    }


def rule_matches(rule: ProjectRule, *, service: str, name: str, labels: dict[str, str]) -> bool:
    value = rule.match_value.strip()
    if rule.match_type == "service":
        compose_service = labels.get(_COMPOSE_SERVICE, "")
        return value in {service, compose_service}
    if rule.match_type == "container_name":
        return value == name
    if rule.match_type == "label":
        if "=" in value:
            key, expected = value.split("=", 1)
            return labels.get(key.strip()) == expected.strip()
        return value in labels
    return False


class ProjectService:
    def __init__(self, projects: ProjectRepository, containers: ContainerRepository) -> None:
        self._projects = projects
        self._containers = containers

    async def create(self, account_id: uuid.UUID, name: str) -> Project:
        slug = slugify(name)
        existing = await self._projects.get_by_slug(account_id, slug)
        if existing is not None:
            return existing
        return await self._projects.add(Project(account_id=account_id, name=name, slug=slug))

    async def add_rule(self, project_id: uuid.UUID, match_type: str, match_value: str) -> ProjectRule:
        return await self._projects.add_rule(
            ProjectRule(project_id=project_id, match_type=match_type, match_value=match_value)
        )

    async def auto_assign(self, account_id: uuid.UUID, record: ContainerStateRecord) -> bool:
        if record.project_id is not None:
            return False
        rules = await self._projects.list_rules_for_account(account_id)
        service = record.labels.get(_COMPOSE_SERVICE, "") if record.labels else ""
        for rule in rules:
            if rule_matches(rule, service=service, name=record.name, labels=record.labels or {}):
                record.project_id = rule.project_id
                return True
        return False

    async def matching_project_ids(self, account_id: uuid.UUID, service: str) -> list[uuid.UUID]:
        rules = await self._projects.list_rules_for_account(account_id)
        matched: set[uuid.UUID] = set()
        for rule in rules:
            if rule.match_type == "service" and rule.match_value.strip() == service.strip():
                matched.add(rule.project_id)
        return list(matched)

    async def project_bot_enabled(self, account_id: uuid.UUID, project_ids: list[uuid.UUID]) -> bool:
        if not project_ids:
            return True
        projects = {project.id: project for project in await self._projects.list_for_account(account_id)}
        return any(projects[project_id].notify_bot for project_id in project_ids if project_id in projects)

    async def set_notify_bot(self, account_id: uuid.UUID, project_id: uuid.UUID, enabled: bool) -> bool:
        project = await self._projects.get(project_id)
        if project is None or project.account_id != account_id:
            return False
        project.notify_bot = enabled
        return True
