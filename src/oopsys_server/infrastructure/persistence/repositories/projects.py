import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_server.infrastructure.persistence.models import Project, ProjectRule


class ProjectRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, project: Project) -> Project:
        self._session.add(project)
        await self._session.flush()
        return project

    async def get(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def get_by_slug(self, account_id: uuid.UUID, slug: str) -> Project | None:
        result = await self._session.execute(select(Project).where(Project.account_id == account_id, Project.slug == slug))
        return result.scalar_one_or_none()

    async def list_for_account(self, account_id: uuid.UUID) -> list[Project]:
        result = await self._session.execute(select(Project).where(Project.account_id == account_id).order_by(Project.name))
        return list(result.scalars().all())

    async def add_rule(self, rule: ProjectRule) -> ProjectRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def list_rules_for_account(self, account_id: uuid.UUID) -> list[ProjectRule]:
        result = await self._session.execute(select(ProjectRule).join(Project, Project.id == ProjectRule.project_id).where(Project.account_id == account_id))
        return list(result.scalars().all())

    async def delete(self, project: Project) -> None:
        await self._session.delete(project)
