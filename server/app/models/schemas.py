from datetime import datetime

from pydantic import BaseModel


class Outcome(BaseModel):
    summary: str
    disposition: str
    next_action: str | None = None


class AgentSummary(BaseModel):
    id: str
    name: str


class CallListItem(BaseModel):
    id: str
    twilio_call_sid: str
    duration_seconds: int | None
    called_at: datetime | None
    status: str
    agent: AgentSummary | None


class CallListResponse(BaseModel):
    data: list[CallListItem]
    total: int
    page: int
    limit: int


class TranscriptDetail(BaseModel):
    redacted_text: str
    whisper_model: str | None


class OutcomeDetail(BaseModel):
    summary: str | None
    disposition: str | None
    next_action: str | None


class CallDetail(BaseModel):
    id: str
    twilio_call_sid: str
    recording_url: str | None
    duration_seconds: int | None
    called_at: datetime | None
    status: str
    agent: AgentSummary | None
    transcript: TranscriptDetail | None
    outcome: OutcomeDetail | None


class AuditEvent(BaseModel):
    id: str
    event: str
    actor: str
    metadata: dict | None
    created_at: datetime


class AuditListResponse(BaseModel):
    data: list[AuditEvent]


class AgentDetail(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime
    total_calls: int
    completed_calls: int


class AgentListResponse(BaseModel):
    data: list[AgentDetail]


class AgentCreate(BaseModel):
    name: str
    email: str
