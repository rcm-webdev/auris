from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_current_session
from app.models.schemas import AuditListResponse, CallDetail, CallListResponse
from app.services import storage

router = APIRouter(prefix="/api/calls", dependencies=[Depends(get_current_session)])


@router.get("", response_model=CallListResponse)
async def list_calls(
    request: Request,
    agent_id: str | None = Query(None),
    status: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    data, total = await storage.list_calls(
        request.app.state.pool, agent_id, status, from_date, to_date, page, limit
    )
    return {"data": [_shape_list_item(r) for r in data], "total": total, "page": page, "limit": limit}


@router.get("/{call_id}", response_model=CallDetail)
async def get_call(call_id: str, request: Request):
    row = await storage.get_call(request.app.state.pool, call_id)
    if not row:
        raise HTTPException(status_code=404, detail="Call not found")
    return _shape_detail(row)


@router.get("/{call_id}/audit", response_model=AuditListResponse)
async def get_call_audit(call_id: str, request: Request):
    rows = await storage.get_call_audit(request.app.state.pool, call_id)
    return {"data": rows}


def _shape_list_item(r: dict) -> dict:
    agent = {"id": r["agent_id"], "name": r["agent_name"]} if r.get("agent_id") else None
    return {k: v for k, v in r.items() if k not in ("agent_id", "agent_name")} | {"agent": agent}


def _shape_detail(r: dict) -> dict:
    agent = {"id": r["agent_id"], "name": r["agent_name"]} if r.get("agent_id") else None
    transcript = (
        {"redacted_text": r["redacted_text"], "whisper_model": r["whisper_model"]}
        if r.get("redacted_text")
        else None
    )
    outcome = (
        {"summary": r["summary"], "disposition": r["disposition"], "next_action": r["next_action"]}
        if r.get("summary")
        else None
    )
    skip = {"agent_id", "agent_name", "redacted_text", "whisper_model", "summary", "disposition", "next_action"}
    return {k: v for k, v in r.items() if k not in skip} | {"agent": agent, "transcript": transcript, "outcome": outcome}
