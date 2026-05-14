import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_current_session
from app.models.schemas import AgentCreate, AgentDetail, AgentListResponse
from app.services import storage

router = APIRouter(prefix="/api/agents", dependencies=[Depends(get_current_session)])


@router.get("", response_model=AgentListResponse)
async def list_agents(request: Request):
    rows = await storage.list_agents(request.app.state.pool)
    return {"data": rows}


@router.post("", response_model=AgentDetail, status_code=201)
async def create_agent(body: AgentCreate, request: Request):
    try:
        row = await storage.create_agent(request.app.state.pool, body.name, body.email)
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Email already in use")
    return row


@router.get("/{agent_id}", response_model=AgentDetail)
async def get_agent(agent_id: str, request: Request):
    row = await storage.get_agent(request.app.state.pool, agent_id)
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    return row
