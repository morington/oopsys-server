from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import getLogger

from oopsys_server.application.ingest import IngestService
from oopsys_server.application.self_errors import SelfErrorReporter
from oopsys_server.application.tokens import AgentTokenService
from oopsys_server.configuration import Loggers
from oopsys_server.domain.envelope import Envelope

logger = getLogger(Loggers.ingest.name)
router = APIRouter(route_class=DishkaRoute, tags=["ingest"])
_bearer = HTTPBearer(auto_error=False)
_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing agent token",
    headers={"WWW-Authenticate": "Bearer"},
)


@router.post("/agents/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    envelope: Envelope,
    token_service: FromDishka[AgentTokenService],
    ingest_service: FromDishka[IngestService],
    self_errors: FromDishka[SelfErrorReporter],
    session: FromDishka[AsyncSession],
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, str]:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED
    token = await token_service.authenticate(credentials.credentials)
    if token is None:
        raise _UNAUTHORIZED
    await token_service.link_agent(token, envelope.agent_id)
    try:
        await ingest_service.handle(envelope)
        await session.commit()
    except ValidationError as exc:
        await session.rollback()
        await self_errors.capture(exc, component="ingest", context={"agent_id": envelope.agent_id})
        await logger.awarning("dropped malformed payload", agent_id=envelope.agent_id, source=envelope.source.value)
        return {"status": "accepted"}
    return {"status": "accepted"}
