import logging

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request
from twilio.request_validator import RequestValidator

from app.config import get_settings
from app.services import extraction, redaction, storage, transcription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks")


async def run_pipeline(pool, call_id: str, recording_url: str) -> None:
    try:
        raw_text, model = await transcription.transcribe(recording_url)
        await storage.update_call_status(pool, call_id, "transcribed")
        await storage.append_audit(pool, call_id, "transcription_completed", {"model": model})

        redacted = redaction.redact(raw_text)
        del raw_text  # PHI boundary — discard raw text immediately

        await storage.save_transcript(pool, call_id, redacted, model)
        await storage.update_call_status(pool, call_id, "redacted")
        await storage.append_audit(pool, call_id, "phi_redacted")

        outcome = await extraction.extract(redacted)
        await storage.save_outcome(pool, call_id, outcome)
        await storage.update_call_status(pool, call_id, "extracted")
        await storage.append_audit(pool, call_id, "outcome_extracted")

    except Exception as exc:
        logger.error("Pipeline failed for call %s: %s", call_id, exc, exc_info=True)
        await storage.update_call_status(pool, call_id, "failed")
        await storage.append_audit(pool, call_id, "step_failed", {"error": str(exc)})


@router.post("/recording")
async def recording_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    CallSid: str = Form(...),
    RecordingUrl: str = Form(...),
    RecordingDuration: str = Form("0"),
    StartTime: str | None = Form(None),
    AgentId: str | None = Form(None),
):
    sig = request.headers.get("X-Twilio-Signature", "")
    form = dict(await request.form())
    if not RequestValidator(get_settings().twilio_auth_token).validate(str(request.url), form, sig):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    pool = request.app.state.pool
    call_id = await storage.upsert_call(
        pool,
        call_sid=CallSid,
        recording_url=RecordingUrl,
        duration_seconds=int(RecordingDuration or 0),
        called_at=StartTime,
        agent_id=AgentId,
    )

    background_tasks.add_task(run_pipeline, pool, call_id, RecordingUrl)
    return {"received": True, "call_id": call_id}
