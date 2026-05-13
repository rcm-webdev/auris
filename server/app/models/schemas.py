from pydantic import BaseModel


class Outcome(BaseModel):
    summary: str
    disposition: str
    next_action: str | None = None
