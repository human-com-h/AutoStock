from pydantic import BaseModel


class HistoryRestoreRequest(BaseModel):
    confirm: str
